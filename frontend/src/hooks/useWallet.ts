import { useState, useCallback, createContext, useContext } from 'react'
import {
  isConnected as fIsConnected,
  requestAccess,
  getPublicKey,
  signTransaction,
} from '@stellar/freighter-api'
import { CONFIG } from '../config'

interface WalletState {
  connected: boolean
  publicKey: string | null
  connecting: boolean
  error: string | null
  /** demo mode = manual key entered, cannot sign transactions */
  canSign: boolean
}

interface WalletContextValue extends WalletState {
  connect: () => Promise<void>
  disconnect: () => void
  /** Sign a transaction XDR with Freighter; returns the signed XDR. */
  signXdr: (xdr: string) => Promise<string>
}

const WalletContext = createContext<WalletContextValue | null>(null)

export function useWalletProvider(): WalletContextValue {
  const [state, setState] = useState<WalletState>({
    connected: false,
    publicKey: null,
    connecting: false,
    error: null,
    canSign: false,
  })

  const connect = useCallback(async () => {
    setState(prev => ({ ...prev, connecting: true, error: null }))
    try {
      // Freighter v2 throws if the extension is absent.
      let available = false
      try {
        available = await fIsConnected()
      } catch {
        available = false
      }

      if (!available) {
        const manualKey = window.prompt(
          'Freighter not detected.\n\nEnter a Stellar public key (G...) for read-only demo mode (cannot sign):'
        )
        if (manualKey && manualKey.startsWith('G') && manualKey.length === 56) {
          setState({ connected: true, publicKey: manualKey, connecting: false, error: null, canSign: false })
          return
        }
        throw new Error('Freighter not found. Install it from freighter.app.')
      }

      await requestAccess()
      const publicKey = await getPublicKey()
      setState({ connected: true, publicKey, connecting: false, error: null, canSign: true })
    } catch (err) {
      setState(prev => ({
        ...prev,
        connecting: false,
        error: err instanceof Error ? err.message : 'Failed to connect wallet',
      }))
    }
  }, [])

  const disconnect = useCallback(() => {
    setState({ connected: false, publicKey: null, connecting: false, error: null, canSign: false })
  }, [])

  const signXdr = useCallback(
    async (xdr: string): Promise<string> => {
      if (!state.canSign) {
        throw new Error('Connect a Freighter wallet to sign transactions (demo mode is read-only).')
      }
      const res = await signTransaction(xdr, {
        networkPassphrase: CONFIG.networkPassphrase,
        accountToSign: state.publicKey || undefined,
      })
      // v2 returns the signed XDR string; some builds wrap it in an object.
      return typeof res === 'string' ? res : (res as { signedTxXdr: string }).signedTxXdr
    },
    [state.canSign, state.publicKey]
  )

  return { ...state, connect, disconnect, signXdr }
}

export { WalletContext }

export function useWallet(): WalletContextValue {
  const ctx = useContext(WalletContext)
  if (!ctx) {
    throw new Error('useWallet must be used within WalletProvider')
  }
  return ctx
}
