#![no_std]

//! DecentraKnow — paid, on-chain semantic search registry.
//!
//! Design (see project discussion):
//! - Embeddings are computed off-chain (local MiniLM, 384d) and compressed into a
//!   256-bit SimHash / random-projection LSH code, stored on-chain as `BytesN<32>`.
//! - `search` ranks records by Hamming distance between the query SimHash and every
//!   stored SimHash. It writes nothing, so it is a *view*: clients run it through
//!   `simulateTransaction` for free. Ranking logic stays on-chain and verifiable.
//! - Searching costs money. The searcher pre-funds a credit balance (`deposit`).
//!   Each settled search (`pay_search`) deducts `search_price` and splits it:
//!   `platform_bps` to the platform (admin), the remainder to the owners of the
//!   records that the search returned. Earnings accrue and are pulled via `withdraw`
//!   (pull-over-push: no fan-out token transfers, no per-search trustline writes).

use soroban_sdk::{
    contract, contracterror, contractimpl, contractmeta, contracttype, symbol_short, token,
    Address, BytesN, Env, String, Vec,
};

contractmeta!(
    key = "desc",
    val = "Paid on-chain semantic search registry: LSH/SimHash Hamming ranking with content-owner fee splitting"
);

// ~5s ledgers. TTL windows keep config and records alive without per-call surprises.
const DAY_IN_LEDGERS: u32 = 17_280;
const INSTANCE_BUMP_AMOUNT: u32 = 30 * DAY_IN_LEDGERS;
const INSTANCE_LIFETIME_THRESHOLD: u32 = INSTANCE_BUMP_AMOUNT - DAY_IN_LEDGERS;
const PERSISTENT_BUMP_AMOUNT: u32 = 90 * DAY_IN_LEDGERS;
const PERSISTENT_LIFETIME_THRESHOLD: u32 = PERSISTENT_BUMP_AMOUNT - DAY_IN_LEDGERS;

const BPS_DENOM: i128 = 10_000;
const MAX_TOP_K: u32 = 50;
const DEFAULT_TOP_K: u32 = 10;

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct KnowledgeRecord {
    pub id: u32,
    pub owner: Address,
    pub content_hash: BytesN<32>,
    pub embedding_hash: BytesN<32>,
    /// 256-bit SimHash (random-projection LSH code of the off-chain embedding).
    pub sim_hash: BytesN<32>,
    pub manifest_cid: String,
    pub source_url: String,
    pub timestamp: u64,
}

/// Compact entry kept in the single packed search index. We deliberately store
/// only `(id, sim_hash)` here so `search` touches exactly one ledger entry and
/// never reads per-record data (which would blow the read footprint).
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct IndexEntry {
    pub id: u32,
    pub sim_hash: BytesN<32>,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SearchHit {
    pub id: u32,
    pub distance: u32,
}

#[contracttype]
pub enum DataKey {
    // --- instance (config + counters, loaded with the contract) ---
    Admin,
    Token,
    SearchPrice,
    PlatformBps,
    RecordCount,
    // --- persistent ---
    Index,
    Record(u32),
    ContentSeen(BytesN<32>),
    Credits(Address),
    Earnings(Address),
}

#[contracterror]
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
#[repr(u32)]
pub enum Error {
    NotInitialized = 1,
    AlreadyInitialized = 2,
    RecordExists = 3,
    RecordNotFound = 4,
    Unauthorized = 5,
    InvalidInput = 6,
    InsufficientCredits = 7,
    NothingToWithdraw = 8,
}

#[contract]
pub struct KnowledgeRegistryContract;

#[contractimpl]
impl KnowledgeRegistryContract {
    /// One-time setup. `search_price` is denominated in the payment token's
    /// smallest unit (e.g. 7-decimal USDC: 1 USDC == 10_000_000).
    pub fn initialize(
        env: Env,
        admin: Address,
        payment_token: Address,
        search_price: i128,
        platform_bps: u32,
    ) -> Result<(), Error> {
        if env.storage().instance().has(&DataKey::Admin) {
            return Err(Error::AlreadyInitialized);
        }
        if search_price <= 0 || platform_bps > BPS_DENOM as u32 {
            return Err(Error::InvalidInput);
        }
        admin.require_auth();

        let s = env.storage().instance();
        s.set(&DataKey::Admin, &admin);
        s.set(&DataKey::Token, &payment_token);
        s.set(&DataKey::SearchPrice, &search_price);
        s.set(&DataKey::PlatformBps, &platform_bps);
        s.set(&DataKey::RecordCount, &0u32);
        extend_instance(&env);
        Ok(())
    }

    /// Register a knowledge record. `owner` authorizes; the off-chain pipeline
    /// supplies the SimHash. Returns the assigned record id.
    pub fn register_knowledge(
        env: Env,
        owner: Address,
        content_hash: BytesN<32>,
        embedding_hash: BytesN<32>,
        sim_hash: BytesN<32>,
        manifest_cid: String,
        source_url: String,
    ) -> Result<u32, Error> {
        require_init(&env)?;
        owner.require_auth();

        let seen_key = DataKey::ContentSeen(content_hash.clone());
        if env.storage().persistent().has(&seen_key) {
            return Err(Error::RecordExists);
        }

        let id = next_id(&env);
        let record = KnowledgeRecord {
            id,
            owner: owner.clone(),
            content_hash: content_hash.clone(),
            embedding_hash,
            sim_hash: sim_hash.clone(),
            manifest_cid,
            source_url,
            timestamp: env.ledger().timestamp(),
        };

        let p = env.storage().persistent();
        p.set(&DataKey::Record(id), &record);
        p.set(&seen_key, &id);

        let mut index: Vec<IndexEntry> = p.get(&DataKey::Index).unwrap_or(Vec::new(&env));
        index.push_back(IndexEntry { id, sim_hash });
        p.set(&DataKey::Index, &index);

        extend_persistent(&env, &DataKey::Record(id));
        extend_persistent(&env, &seen_key);
        extend_persistent(&env, &DataKey::Index);
        extend_instance(&env);

        env.events()
            .publish((symbol_short!("register"), owner), id);
        Ok(id)
    }

    /// On-chain similarity search. Pure read → run via `simulateTransaction` for
    /// free. Returns up to `top_k` record ids ordered by ascending Hamming
    /// distance (smaller = more similar).
    pub fn search(env: Env, query: BytesN<32>, top_k: u32) -> Vec<SearchHit> {
        let k = if top_k == 0 || top_k > MAX_TOP_K {
            DEFAULT_TOP_K
        } else {
            top_k
        };

        let index: Vec<IndexEntry> = env
            .storage()
            .persistent()
            .get(&DataKey::Index)
            .unwrap_or(Vec::new(&env));

        let mut hits: Vec<SearchHit> = Vec::new(&env);
        for entry in index.iter() {
            let distance = hamming_distance(&query, &entry.sim_hash);

            // Insert keeping `hits` sorted ascending, capped at k.
            let mut pos = hits.len();
            let mut i = 0u32;
            for h in hits.iter() {
                if distance < h.distance {
                    pos = i;
                    break;
                }
                i += 1;
            }
            if pos < k {
                hits.insert(pos, SearchHit { id: entry.id, distance });
                while hits.len() > k {
                    hits.pop_back();
                }
            }
        }
        hits
    }

    /// Pre-fund the caller's search credit by transferring `amount` of the
    /// payment token into the contract. Returns the new credit balance.
    pub fn deposit(env: Env, from: Address, amount: i128) -> Result<i128, Error> {
        require_init(&env)?;
        from.require_auth();
        if amount <= 0 {
            return Err(Error::InvalidInput);
        }

        let token_addr = get_token(&env);
        token::Client::new(&env, &token_addr).transfer(
            &from,
            &env.current_contract_address(),
            &amount,
        );

        let key = DataKey::Credits(from.clone());
        let balance: i128 = env.storage().persistent().get(&key).unwrap_or(0) + amount;
        env.storage().persistent().set(&key, &balance);
        extend_persistent(&env, &key);
        extend_instance(&env);

        env.events().publish((symbol_short!("deposit"), from), amount);
        Ok(balance)
    }

    /// Settle one search: deduct `search_price` from `payer`'s credit and split it
    /// between the platform and the owners of the returned records.
    ///
    /// Called by the platform operator (admin auth) after running the search, so
    /// no per-search wallet prompt is needed. `result_ids` are the records the
    /// search returned; the contract resolves each id to its real owner itself,
    /// so the operator cannot invent payees — only pick existing records. The
    /// per-call deduction is fixed at `search_price`, bounding operator abuse.
    pub fn pay_search(env: Env, payer: Address, result_ids: Vec<u32>) -> Result<(), Error> {
        require_init(&env)?;
        let admin = get_admin(&env);
        admin.require_auth();

        if result_ids.is_empty() {
            return Err(Error::InvalidInput);
        }

        let price = get_search_price(&env);
        let credits_key = DataKey::Credits(payer.clone());
        let credits: i128 = env.storage().persistent().get(&credits_key).unwrap_or(0);
        if credits < price {
            return Err(Error::InsufficientCredits);
        }
        env.storage()
            .persistent()
            .set(&credits_key, &(credits - price));
        extend_persistent(&env, &credits_key);

        let platform_bps = get_platform_bps(&env) as i128;
        let platform_cut = price * platform_bps / BPS_DENOM;
        let owner_pool = price - platform_cut;
        let n = result_ids.len() as i128;
        let share = owner_pool / n;

        let mut distributed: i128 = 0;
        for id in result_ids.iter() {
            let record: KnowledgeRecord = env
                .storage()
                .persistent()
                .get(&DataKey::Record(id))
                .ok_or(Error::RecordNotFound)?;
            credit_earnings(&env, &record.owner, share);
            distributed += share;
        }

        // Platform gets its cut plus any integer-division remainder (no dust lost).
        let platform_total = price - distributed;
        credit_earnings(&env, &admin, platform_total);

        extend_instance(&env);
        env.events()
            .publish((symbol_short!("paysearch"), payer), price);
        Ok(())
    }

    /// Refund unspent search credit. The searcher pulls back deposited funds that
    /// they have not yet spent on searches. Returns the remaining credit balance.
    pub fn withdraw_credits(env: Env, to: Address, amount: i128) -> Result<i128, Error> {
        require_init(&env)?;
        to.require_auth();
        if amount <= 0 {
            return Err(Error::InvalidInput);
        }

        let key = DataKey::Credits(to.clone());
        let balance: i128 = env.storage().persistent().get(&key).unwrap_or(0);
        if balance < amount {
            return Err(Error::InsufficientCredits);
        }
        let remaining = balance - amount;
        env.storage().persistent().set(&key, &remaining);
        extend_persistent(&env, &key);

        let token_addr = get_token(&env);
        token::Client::new(&env, &token_addr).transfer(
            &env.current_contract_address(),
            &to,
            &amount,
        );

        extend_instance(&env);
        env.events().publish((symbol_short!("refund"), to), amount);
        Ok(remaining)
    }

    /// Withdraw accrued earnings to `to`. Works for content owners and the
    /// platform alike.
    pub fn withdraw(env: Env, to: Address) -> Result<i128, Error> {
        require_init(&env)?;
        to.require_auth();

        let key = DataKey::Earnings(to.clone());
        let amount: i128 = env.storage().persistent().get(&key).unwrap_or(0);
        if amount <= 0 {
            return Err(Error::NothingToWithdraw);
        }
        env.storage().persistent().set(&key, &0i128);

        let token_addr = get_token(&env);
        token::Client::new(&env, &token_addr).transfer(
            &env.current_contract_address(),
            &to,
            &amount,
        );

        extend_instance(&env);
        env.events().publish((symbol_short!("withdraw"), to), amount);
        Ok(amount)
    }

    // ----------------------------- views -----------------------------

    pub fn get_record(env: Env, id: u32) -> Result<KnowledgeRecord, Error> {
        env.storage()
            .persistent()
            .get(&DataKey::Record(id))
            .ok_or(Error::RecordNotFound)
    }

    pub fn get_credits(env: Env, user: Address) -> i128 {
        env.storage()
            .persistent()
            .get(&DataKey::Credits(user))
            .unwrap_or(0)
    }

    pub fn get_earnings(env: Env, user: Address) -> i128 {
        env.storage()
            .persistent()
            .get(&DataKey::Earnings(user))
            .unwrap_or(0)
    }

    pub fn get_record_count(env: Env) -> u32 {
        env.storage()
            .instance()
            .get(&DataKey::RecordCount)
            .unwrap_or(0)
    }

    pub fn get_search_price(env: Env) -> i128 {
        get_search_price(&env)
    }

    pub fn get_platform_bps(env: Env) -> u32 {
        get_platform_bps(&env)
    }

    // --------------------------- admin ops ---------------------------

    pub fn set_search_price(env: Env, new_price: i128) -> Result<(), Error> {
        require_init(&env)?;
        get_admin(&env).require_auth();
        if new_price <= 0 {
            return Err(Error::InvalidInput);
        }
        env.storage()
            .instance()
            .set(&DataKey::SearchPrice, &new_price);
        extend_instance(&env);
        Ok(())
    }

    pub fn set_platform_bps(env: Env, new_bps: u32) -> Result<(), Error> {
        require_init(&env)?;
        get_admin(&env).require_auth();
        if new_bps > BPS_DENOM as u32 {
            return Err(Error::InvalidInput);
        }
        env.storage()
            .instance()
            .set(&DataKey::PlatformBps, &new_bps);
        extend_instance(&env);
        Ok(())
    }
}

// =============================== helpers ===============================

/// 256-bit Hamming distance: XOR + popcount, byte by byte. Cheap enough that a
/// full-index scan stays well inside the CPU budget.
fn hamming_distance(a: &BytesN<32>, b: &BytesN<32>) -> u32 {
    let a = a.to_array();
    let b = b.to_array();
    let mut distance = 0u32;
    let mut i = 0usize;
    while i < 32 {
        distance += (a[i] ^ b[i]).count_ones();
        i += 1;
    }
    distance
}

fn require_init(env: &Env) -> Result<(), Error> {
    if env.storage().instance().has(&DataKey::Admin) {
        Ok(())
    } else {
        Err(Error::NotInitialized)
    }
}

fn next_id(env: &Env) -> u32 {
    let count: u32 = env
        .storage()
        .instance()
        .get(&DataKey::RecordCount)
        .unwrap_or(0);
    env.storage()
        .instance()
        .set(&DataKey::RecordCount, &(count + 1));
    count
}

fn credit_earnings(env: &Env, who: &Address, amount: i128) {
    if amount == 0 {
        return;
    }
    let key = DataKey::Earnings(who.clone());
    let balance: i128 = env.storage().persistent().get(&key).unwrap_or(0) + amount;
    env.storage().persistent().set(&key, &balance);
    extend_persistent(env, &key);
}

fn get_admin(env: &Env) -> Address {
    env.storage().instance().get(&DataKey::Admin).unwrap()
}

fn get_token(env: &Env) -> Address {
    env.storage().instance().get(&DataKey::Token).unwrap()
}

fn get_search_price(env: &Env) -> i128 {
    env.storage().instance().get(&DataKey::SearchPrice).unwrap()
}

fn get_platform_bps(env: &Env) -> u32 {
    env.storage().instance().get(&DataKey::PlatformBps).unwrap()
}

fn extend_instance(env: &Env) {
    env.storage()
        .instance()
        .extend_ttl(INSTANCE_LIFETIME_THRESHOLD, INSTANCE_BUMP_AMOUNT);
}

fn extend_persistent(env: &Env, key: &DataKey) {
    env.storage().persistent().extend_ttl(
        key,
        PERSISTENT_LIFETIME_THRESHOLD,
        PERSISTENT_BUMP_AMOUNT,
    );
}

#[cfg(test)]
mod test;
