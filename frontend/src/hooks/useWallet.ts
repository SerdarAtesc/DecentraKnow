import { useState, useCallback, createContext, useContext } from 'react'

interface WalletState {
  connected: boolean
  publicKey: string | null
  connecting: boolean
  error: string | null
}

interface WalletContextValue extends WalletState {
  connect: () => Promise<void>
  disconnect: () => void
}

const WalletContext = createContext<WalletContextValue | null>(null)

async function getFreighterApi() {
  const win = window as unknown as Record<string, unknown>

  if (win.freighterApi && typeof win.freighterApi === 'object') {
    return win.freighterApi as {
      isConnected: () => Promise<boolean>
      getPublicKey: () => Promise<string>
      requestAccess: () => Promise<string>
    }
  }

  if (win.freighter && typeof win.freighter === 'object') {
    return win.freighter as {
      isConnected: () => Promise<boolean>
      getPublicKey: () => Promise<string>
      requestAccess: () => Promise<string>
    }
  }

  return null
}

export function useWalletProvider(): WalletContextValue {
  const [state, setState] = useState<WalletState>({
    connected: false,
    publicKey: null,
    connecting: false,
    error: null,
  })

  const connect = useCallback(async () => {
    setState(prev => ({ ...prev, connecting: true, error: null }))

    try {
      const freighter = await getFreighterApi()

      if (!freighter) {
        const manualKey = window.prompt(
          'Freighter wallet extension not detected.\n\nEnter your Stellar public key (G...) to continue in demo mode:'
        )
        if (manualKey && manualKey.startsWith('G') && manualKey.length === 56) {
          setState({
            connected: true,
            publicKey: manualKey,
            connecting: false,
            error: null,
          })
          return
        }
        throw new Error(
          'Freighter wallet not found. Install it from freighter.app or enter a valid public key.'
        )
      }

      const isConnected = await freighter.isConnected()
      if (!isConnected) {
        await freighter.requestAccess()
      }

      const publicKey = await freighter.getPublicKey()
      setState({
        connected: true,
        publicKey,
        connecting: false,
        error: null,
      })
    } catch (err) {
      setState(prev => ({
        ...prev,
        connecting: false,
        error: err instanceof Error ? err.message : 'Failed to connect wallet',
      }))
    }
  }, [])

  const disconnect = useCallback(() => {
    setState({
      connected: false,
      publicKey: null,
      connecting: false,
      error: null,
    })
  }, [])

  return { ...state, connect, disconnect }
}

export { WalletContext }

export function useWallet(): WalletContextValue {
  const ctx = useContext(WalletContext)
  if (!ctx) {
    throw new Error('useWallet must be used within WalletProvider')
  }
  return ctx
}
