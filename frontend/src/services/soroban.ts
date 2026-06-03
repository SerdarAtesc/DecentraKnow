// Client-side Soroban contract calls signed by the user's Freighter wallet.
// Stellar SDK v14: the RPC namespace is `rpc` (not SorobanRpc).

import {
  rpc,
  TransactionBuilder,
  Contract,
  Address,
  nativeToScVal,
  scValToNative,
  BASE_FEE,
  xdr,
} from '@stellar/stellar-sdk'
import { CONFIG, toStroops } from '../config'

const server = new rpc.Server(CONFIG.rpcUrl)

const addr = (pk: string): xdr.ScVal => new Address(pk).toScVal()
const i128 = (amount: bigint): xdr.ScVal => nativeToScVal(amount, { type: 'i128' })
const str = (s: string): xdr.ScVal => nativeToScVal(s, { type: 'string' })

function hexToBytes(hex: string): Uint8Array {
  const clean = hex.startsWith('0x') ? hex.slice(2) : hex
  const out = new Uint8Array(clean.length / 2)
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(clean.slice(i * 2, i * 2 + 2), 16)
  }
  return out
}
const bytes32 = (hex: string): xdr.ScVal => nativeToScVal(hexToBytes(hex), { type: 'bytes' })

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

type SignFn = (xdr: string) => Promise<string>

/**
 * Build → simulate/prepare → wallet-sign → submit → poll a state-changing
 * contract call. Returns the decoded return value (or null).
 */
async function invokeSigned(
  publicKey: string,
  signXdr: SignFn,
  method: string,
  args: xdr.ScVal[]
): Promise<unknown> {
  const account = await server.getAccount(publicKey)
  const contract = new Contract(CONFIG.contractId)

  const built = new TransactionBuilder(account, {
    fee: BASE_FEE,
    networkPassphrase: CONFIG.networkPassphrase,
  })
    .addOperation(contract.call(method, ...args))
    .setTimeout(180)
    .build()

  // prepareTransaction simulates and assembles auth + resource footprint.
  const prepared = await server.prepareTransaction(built)
  const signedXdr = await signXdr(prepared.toXDR())
  const signedTx = TransactionBuilder.fromXDR(signedXdr, CONFIG.networkPassphrase)

  const sent = await server.sendTransaction(signedTx)
  if (sent.status === 'ERROR') {
    throw new Error(`Transaction submission failed for ${method}`)
  }

  let got = await server.getTransaction(sent.hash)
  for (let i = 0; i < 30 && got.status === rpc.Api.GetTransactionStatus.NOT_FOUND; i++) {
    await sleep(1000)
    got = await server.getTransaction(sent.hash)
  }
  if (got.status !== rpc.Api.GetTransactionStatus.SUCCESS) {
    throw new Error(`Transaction failed on-chain for ${method}: ${got.status}`)
  }

  const ret = got.returnValue
  return ret ? scValToNative(ret) : null
}

// ---- wallet-signed operations ----

export interface RegisterFields {
  contentHash: string
  embeddingHash: string
  simHash: string
  ipfsCid: string
  sourceUrl: string
}

export const soroban = {
  /** Register a knowledge record signed by the owner's wallet. Returns the on-chain id. */
  register: (pk: string, sign: SignFn, f: RegisterFields) =>
    invokeSigned(pk, sign, 'register_knowledge', [
      addr(pk),
      bytes32(f.contentHash),
      bytes32(f.embeddingHash),
      bytes32(f.simHash),
      str(f.ipfsCid),
      str(f.sourceUrl || ''),
    ]) as Promise<number>,

  /** Deposit XLM into search credit. amount in XLM. */
  deposit: (pk: string, sign: SignFn, amountXlm: number | string) =>
    invokeSigned(pk, sign, 'deposit', [addr(pk), i128(toStroops(amountXlm))]),

  /** Withdraw accrued earnings to the wallet. */
  withdraw: (pk: string, sign: SignFn) =>
    invokeSigned(pk, sign, 'withdraw', [addr(pk)]),

  /** Refund unspent search credit. amount in XLM. */
  withdrawCredits: (pk: string, sign: SignFn, amountXlm: number | string) =>
    invokeSigned(pk, sign, 'withdraw_credits', [addr(pk), i128(toStroops(amountXlm))]),
}

export { server as sorobanServer }
