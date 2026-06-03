#![cfg(test)]

use super::*;
use soroban_sdk::testutils::{Address as _, Ledger};
use soroban_sdk::{token, vec, Address, BytesN, Env, String};

const PRICE: i128 = 10_000_000; // 1 USDC (7 decimals)
const PLATFORM_BPS: u32 = 3_000; // 30%

struct Setup {
    env: Env,
    client: KnowledgeRegistryContractClient<'static>,
    admin: Address,
    token: token::Client<'static>,
    token_admin: token::StellarAssetClient<'static>,
}

fn setup() -> Setup {
    let env = Env::default();
    env.mock_all_auths();

    let admin = Address::generate(&env);

    // Deploy a Stellar Asset Contract to stand in for USDC.
    let issuer = Address::generate(&env);
    let sac = env.register_stellar_asset_contract_v2(issuer);
    let token_addr = sac.address();
    let token = token::Client::new(&env, &token_addr);
    let token_admin = token::StellarAssetClient::new(&env, &token_addr);

    let contract_id = env.register_contract(None, KnowledgeRegistryContract);
    let client = KnowledgeRegistryContractClient::new(&env, &contract_id);
    client.initialize(&admin, &token_addr, &PRICE, &PLATFORM_BPS);

    Setup {
        env,
        client,
        admin,
        token,
        token_admin,
    }
}

fn hash(env: &Env, fill: u8) -> BytesN<32> {
    BytesN::from_array(env, &[fill; 32])
}

/// SimHash with exactly `bits` low-order bits set → Hamming distance `bits`
/// from the all-zero query.
fn simhash_with_bits(env: &Env, bits: u32) -> BytesN<32> {
    let mut arr = [0u8; 32];
    let mut remaining = bits;
    let mut byte = 0usize;
    while remaining > 0 && byte < 32 {
        let take = core::cmp::min(remaining, 8);
        arr[byte] = ((1u16 << take) - 1) as u8;
        remaining -= take;
        byte += 1;
    }
    BytesN::from_array(env, &arr)
}

fn register(s: &Setup, owner: &Address, content_fill: u8, sim_hash: &BytesN<32>) -> u32 {
    s.client.register_knowledge(
        owner,
        &hash(&s.env, content_fill),
        &hash(&s.env, content_fill.wrapping_add(100)),
        sim_hash,
        &String::from_str(&s.env, "QmCID"),
        &String::from_str(&s.env, "https://example.com"),
    )
}

#[test]
fn test_initialize() {
    let s = setup();
    assert_eq!(s.client.get_record_count(), 0);
    assert_eq!(s.client.get_search_price(), PRICE);
    assert_eq!(s.client.get_platform_bps(), PLATFORM_BPS);
}

#[test]
#[should_panic]
fn test_double_initialize_fails() {
    let s = setup();
    s.client
        .initialize(&s.admin, &s.token.address, &PRICE, &PLATFORM_BPS);
}

#[test]
fn test_register_and_get() {
    let s = setup();
    s.env.ledger().set_timestamp(1_700_000_000);
    let owner = Address::generate(&s.env);
    let sim = simhash_with_bits(&s.env, 3);

    let id = register(&s, &owner, 1, &sim);
    assert_eq!(id, 0);
    assert_eq!(s.client.get_record_count(), 1);

    let record = s.client.get_record(&id);
    assert_eq!(record.owner, owner);
    assert_eq!(record.sim_hash, sim);
    assert_eq!(record.timestamp, 1_700_000_000);
}

#[test]
#[should_panic]
fn test_duplicate_content_rejected() {
    let s = setup();
    let owner = Address::generate(&s.env);
    let sim = simhash_with_bits(&s.env, 1);
    register(&s, &owner, 7, &sim);
    // Same content_hash (fill = 7) → RecordExists.
    register(&s, &owner, 7, &sim);
}

#[test]
fn test_search_ranks_by_hamming_distance() {
    let s = setup();
    let owner = Address::generate(&s.env);

    // Query is the all-zero hash; distance == number of set bits.
    let id_far = register(&s, &owner, 1, &simhash_with_bits(&s.env, 20));
    let id_near = register(&s, &owner, 2, &simhash_with_bits(&s.env, 1));
    let id_mid = register(&s, &owner, 3, &simhash_with_bits(&s.env, 5));

    let query = hash(&s.env, 0);
    let hits = s.client.search(&query, &2);

    assert_eq!(hits.len(), 2);
    // Closest first.
    assert_eq!(hits.get(0).unwrap().id, id_near);
    assert_eq!(hits.get(0).unwrap().distance, 1);
    assert_eq!(hits.get(1).unwrap().id, id_mid);
    assert_eq!(hits.get(1).unwrap().distance, 5);
    let _ = id_far;
}

#[test]
fn test_deposit_increments_credits() {
    let s = setup();
    let user = Address::generate(&s.env);
    s.token_admin.mint(&user, &(5 * PRICE));

    let bal = s.client.deposit(&user, &(3 * PRICE));
    assert_eq!(bal, 3 * PRICE);
    assert_eq!(s.client.get_credits(&user), 3 * PRICE);
    // Tokens moved into the contract.
    assert_eq!(s.token.balance(&user), 2 * PRICE);
}

#[test]
fn test_pay_search_splits_fee() {
    let s = setup();
    let searcher = Address::generate(&s.env);
    let owner_a = Address::generate(&s.env);
    let owner_b = Address::generate(&s.env);

    s.token_admin.mint(&searcher, &(10 * PRICE));
    s.client.deposit(&searcher, &(10 * PRICE));

    let id_a = register(&s, &owner_a, 1, &simhash_with_bits(&s.env, 1));
    let id_b = register(&s, &owner_b, 2, &simhash_with_bits(&s.env, 2));

    s.client
        .pay_search(&searcher, &vec![&s.env, id_a, id_b]);

    // Credit deducted by exactly one search price.
    assert_eq!(s.client.get_credits(&searcher), 9 * PRICE);

    // 30% platform cut = 3_000_000; owner pool = 7_000_000 split two ways.
    let platform_cut = PRICE * PLATFORM_BPS as i128 / 10_000;
    let owner_pool = PRICE - platform_cut;
    let share = owner_pool / 2;
    assert_eq!(s.client.get_earnings(&owner_a), share);
    assert_eq!(s.client.get_earnings(&owner_b), share);
    // Platform keeps cut + any rounding remainder; nothing is lost.
    assert_eq!(s.client.get_earnings(&s.admin), PRICE - 2 * share);
    assert_eq!(
        s.client.get_earnings(&owner_a)
            + s.client.get_earnings(&owner_b)
            + s.client.get_earnings(&s.admin),
        PRICE
    );
}

#[test]
fn test_pay_search_remainder_to_platform() {
    let s = setup();
    let searcher = Address::generate(&s.env);
    let owners: [Address; 3] = [
        Address::generate(&s.env),
        Address::generate(&s.env),
        Address::generate(&s.env),
    ];
    s.token_admin.mint(&searcher, &PRICE);
    s.client.deposit(&searcher, &PRICE);

    let ids = vec![
        &s.env,
        register(&s, &owners[0], 1, &simhash_with_bits(&s.env, 1)),
        register(&s, &owners[1], 2, &simhash_with_bits(&s.env, 2)),
        register(&s, &owners[2], 3, &simhash_with_bits(&s.env, 3)),
    ];
    s.client.pay_search(&searcher, &ids);

    let owner_pool = PRICE - (PRICE * PLATFORM_BPS as i128 / 10_000);
    let share = owner_pool / 3;
    let total = s.client.get_earnings(&owners[0])
        + s.client.get_earnings(&owners[1])
        + s.client.get_earnings(&owners[2])
        + s.client.get_earnings(&s.admin);
    assert_eq!(share, owner_pool / 3);
    assert_eq!(total, PRICE); // conservation: no dust lost
}

#[test]
#[should_panic]
fn test_pay_search_insufficient_credits() {
    let s = setup();
    let searcher = Address::generate(&s.env);
    let owner = Address::generate(&s.env);
    let id = register(&s, &owner, 1, &simhash_with_bits(&s.env, 1));
    // No deposit → no credits.
    s.client.pay_search(&searcher, &vec![&s.env, id]);
}

#[test]
fn test_withdraw_transfers_and_zeroes() {
    let s = setup();
    let searcher = Address::generate(&s.env);
    let owner = Address::generate(&s.env);

    s.token_admin.mint(&searcher, &PRICE);
    s.client.deposit(&searcher, &PRICE);
    let id = register(&s, &owner, 1, &simhash_with_bits(&s.env, 1));
    s.client.pay_search(&searcher, &vec![&s.env, id]);

    let earnings = s.client.get_earnings(&owner);
    assert!(earnings > 0);

    let withdrawn = s.client.withdraw(&owner);
    assert_eq!(withdrawn, earnings);
    assert_eq!(s.client.get_earnings(&owner), 0);
    assert_eq!(s.token.balance(&owner), earnings);
}

#[test]
#[should_panic]
fn test_withdraw_nothing_fails() {
    let s = setup();
    let nobody = Address::generate(&s.env);
    s.client.withdraw(&nobody);
}

#[test]
fn test_withdraw_credits_refunds_unspent() {
    let s = setup();
    let user = Address::generate(&s.env);
    s.token_admin.mint(&user, &(5 * PRICE));
    s.client.deposit(&user, &(5 * PRICE));

    // Refund 2 of the 5 deposited.
    let remaining = s.client.withdraw_credits(&user, &(2 * PRICE));
    assert_eq!(remaining, 3 * PRICE);
    assert_eq!(s.client.get_credits(&user), 3 * PRICE);
    // 2 back in the wallet, 3 still held by the contract.
    assert_eq!(s.token.balance(&user), 2 * PRICE);
}

#[test]
#[should_panic]
fn test_withdraw_credits_over_balance_fails() {
    let s = setup();
    let user = Address::generate(&s.env);
    s.token_admin.mint(&user, &PRICE);
    s.client.deposit(&user, &PRICE);
    s.client.withdraw_credits(&user, &(2 * PRICE));
}

#[test]
fn test_admin_can_update_price() {
    let s = setup();
    s.client.set_search_price(&(2 * PRICE));
    assert_eq!(s.client.get_search_price(), 2 * PRICE);
    s.client.set_platform_bps(&5_000);
    assert_eq!(s.client.get_platform_bps(), 5_000);
}
