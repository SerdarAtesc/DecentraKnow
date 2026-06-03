// On-chain config for the deployed knowledge-registry contract.
// Override via Vite env (VITE_*) for other deployments.

export const CONFIG = {
  contractId:
    import.meta.env.VITE_CONTRACT_ID ||
    'CDW74FDBH4BIK3NT75D7XRI5T52ZWUISWWFLCQ6IPKEL6XVCMOKEJSIF',
  rpcUrl: import.meta.env.VITE_SOROBAN_RPC || 'https://soroban-testnet.stellar.org',
  networkPassphrase:
    import.meta.env.VITE_NETWORK_PASSPHRASE || 'Test SDF Network ; September 2015',
  // XLM has 7 decimals: 1 XLM = 10_000_000 stroops.
  decimals: 7,
}

export const STROOPS_PER_XLM = 10 ** CONFIG.decimals

export function toStroops(xlm: number | string): bigint {
  // Avoid float drift: scale via string math.
  const n = typeof xlm === 'string' ? parseFloat(xlm) : xlm
  return BigInt(Math.round(n * STROOPS_PER_XLM))
}

export function toXlm(stroops: number | string | bigint): string {
  const s = typeof stroops === 'bigint' ? stroops : BigInt(Math.trunc(Number(stroops)))
  const whole = s / BigInt(STROOPS_PER_XLM)
  const frac = (s % BigInt(STROOPS_PER_XLM)).toString().padStart(CONFIG.decimals, '0').replace(/0+$/, '')
  return frac ? `${whole}.${frac}` : `${whole}`
}
