#![no_std]

use soroban_sdk::{
    contract, contractimpl, contracttype, contracterror, symbol_short, Address, BytesN, Env,
    String, Vec,
};

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct KnowledgeRecord {
    pub owner: Address,
    pub content_hash: BytesN<32>,
    pub embedding_hash: BytesN<32>,
    pub manifest_cid: String,
    pub source_url: String,
    pub timestamp: u64,
}

#[contracttype]
pub enum DataKey {
    Record(BytesN<32>),
    RecordCount,
    OwnerRecords(Address),
    Admin,
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
}

#[contract]
pub struct KnowledgeRegistryContract;

#[contractimpl]
impl KnowledgeRegistryContract {
    pub fn initialize(env: Env, admin: Address) -> Result<(), Error> {
        if env.storage().instance().has(&DataKey::Admin) {
            return Err(Error::AlreadyInitialized);
        }
        admin.require_auth();
        env.storage().instance().set(&DataKey::Admin, &admin);
        env.storage().instance().set(&DataKey::RecordCount, &0u64);
        Ok(())
    }

    pub fn register_knowledge(
        env: Env,
        owner: Address,
        content_hash: BytesN<32>,
        embedding_hash: BytesN<32>,
        manifest_cid: String,
        source_url: String,
    ) -> Result<BytesN<32>, Error> {
        owner.require_auth();

        if env.storage().persistent().has(&DataKey::Record(content_hash.clone())) {
            return Err(Error::RecordExists);
        }

        let timestamp = env.ledger().timestamp();

        let record = KnowledgeRecord {
            owner: owner.clone(),
            content_hash: content_hash.clone(),
            embedding_hash,
            manifest_cid,
            source_url,
            timestamp,
        };

        env.storage()
            .persistent()
            .set(&DataKey::Record(content_hash.clone()), &record);

        let mut owner_records: Vec<BytesN<32>> = env
            .storage()
            .persistent()
            .get(&DataKey::OwnerRecords(owner.clone()))
            .unwrap_or(Vec::new(&env));
        owner_records.push_back(content_hash.clone());
        env.storage()
            .persistent()
            .set(&DataKey::OwnerRecords(owner), &owner_records);

        let count: u64 = env
            .storage()
            .instance()
            .get(&DataKey::RecordCount)
            .unwrap_or(0);
        env.storage()
            .instance()
            .set(&DataKey::RecordCount, &(count + 1));

        env.events().publish(
            (symbol_short!("register"),),
            content_hash.clone(),
        );

        Ok(content_hash)
    }

    pub fn get_record(env: Env, content_hash: BytesN<32>) -> Result<KnowledgeRecord, Error> {
        env.storage()
            .persistent()
            .get(&DataKey::Record(content_hash))
            .ok_or(Error::RecordNotFound)
    }

    pub fn verify_integrity(
        env: Env,
        content_hash: BytesN<32>,
        expected_embedding_hash: BytesN<32>,
    ) -> Result<bool, Error> {
        let record: KnowledgeRecord = env
            .storage()
            .persistent()
            .get(&DataKey::Record(content_hash))
            .ok_or(Error::RecordNotFound)?;

        Ok(record.embedding_hash == expected_embedding_hash)
    }

    pub fn get_owner_records(env: Env, owner: Address) -> Vec<BytesN<32>> {
        env.storage()
            .persistent()
            .get(&DataKey::OwnerRecords(owner))
            .unwrap_or(Vec::new(&env))
    }

    pub fn get_record_count(env: Env) -> u64 {
        env.storage()
            .instance()
            .get(&DataKey::RecordCount)
            .unwrap_or(0)
    }

    pub fn transfer_ownership(
        env: Env,
        content_hash: BytesN<32>,
        current_owner: Address,
        new_owner: Address,
    ) -> Result<(), Error> {
        current_owner.require_auth();

        let mut record: KnowledgeRecord = env
            .storage()
            .persistent()
            .get(&DataKey::Record(content_hash.clone()))
            .ok_or(Error::RecordNotFound)?;

        if record.owner != current_owner {
            return Err(Error::Unauthorized);
        }

        record.owner = new_owner.clone();
        env.storage()
            .persistent()
            .set(&DataKey::Record(content_hash.clone()), &record);

        let mut old_records: Vec<BytesN<32>> = env
            .storage()
            .persistent()
            .get(&DataKey::OwnerRecords(current_owner.clone()))
            .unwrap_or(Vec::new(&env));

        if let Some(idx) = old_records.iter().position(|r| r == content_hash) {
            old_records.remove(idx as u32);
        }
        env.storage()
            .persistent()
            .set(&DataKey::OwnerRecords(current_owner), &old_records);

        let mut new_records: Vec<BytesN<32>> = env
            .storage()
            .persistent()
            .get(&DataKey::OwnerRecords(new_owner.clone()))
            .unwrap_or(Vec::new(&env));
        new_records.push_back(content_hash);
        env.storage()
            .persistent()
            .set(&DataKey::OwnerRecords(new_owner), &new_records);

        Ok(())
    }
}

#[cfg(test)]
mod test {
    use super::*;
    use soroban_sdk::testutils::{Address as _, Ledger};
    use soroban_sdk::Env;

    #[test]
    fn test_initialize() {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register(KnowledgeRegistryContract, ());
        let client = KnowledgeRegistryContractClient::new(&env, &contract_id);

        let admin = Address::generate(&env);
        client.initialize(&admin);

        assert_eq!(client.get_record_count(), 0);
    }

    #[test]
    fn test_register_and_retrieve() {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register(KnowledgeRegistryContract, ());
        let client = KnowledgeRegistryContractClient::new(&env, &contract_id);

        let admin = Address::generate(&env);
        client.initialize(&admin);

        let owner = Address::generate(&env);
        let content_hash = BytesN::from_array(&env, &[1u8; 32]);
        let embedding_hash = BytesN::from_array(&env, &[2u8; 32]);
        let manifest_cid = String::from_str(&env, "QmTestCID12345");
        let source_url = String::from_str(&env, "https://example.com/doc");

        env.ledger().set_timestamp(1_700_000_000);

        let result = client.register_knowledge(
            &owner,
            &content_hash,
            &embedding_hash,
            &manifest_cid,
            &source_url,
        );
        assert_eq!(result, content_hash);
        assert_eq!(client.get_record_count(), 1);

        let record = client.get_record(&content_hash);
        assert_eq!(record.owner, owner);
        assert_eq!(record.timestamp, 1_700_000_000);
    }

    #[test]
    fn test_verify_integrity() {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register(KnowledgeRegistryContract, ());
        let client = KnowledgeRegistryContractClient::new(&env, &contract_id);

        let admin = Address::generate(&env);
        client.initialize(&admin);

        let owner = Address::generate(&env);
        let content_hash = BytesN::from_array(&env, &[1u8; 32]);
        let embedding_hash = BytesN::from_array(&env, &[2u8; 32]);
        let manifest_cid = String::from_str(&env, "QmTestCID");
        let source_url = String::from_str(&env, "https://example.com");

        client.register_knowledge(&owner, &content_hash, &embedding_hash, &manifest_cid, &source_url);

        assert!(client.verify_integrity(&content_hash, &embedding_hash));

        let wrong_hash = BytesN::from_array(&env, &[9u8; 32]);
        assert!(!client.verify_integrity(&content_hash, &wrong_hash));
    }
}
