'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
    const [passcode, setPasscode] = useState('')
    const [error, setError] = useState('')
    const router = useRouter()

    const handleLogin = (e: React.FormEvent) => {
        e.preventDefault()

        // Hardcoded passcode for Pilot
        if (passcode === '1234') {
            // Set cookie (valid for 1 day)
            document.cookie = "auth_token=valid; path=/; max-age=86400"
            router.push('/')
            router.refresh()
        } else {
            setError('Invalid Passcode')
        }
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
            <div className="w-full max-w-sm bg-white p-8 rounded-xl shadow-md border border-gray-100">
                <h1 className="text-xl font-bold text-center text-gray-900 mb-6">MarketPulse-Reg 🔒</h1>

                <form onSubmit={handleLogin} className="space-y-4">
                    <div>
                        <label htmlFor="passcode" className="block text-sm font-medium text-gray-700 mb-1">
                            Enter Passcode
                        </label>
                        <input
                            type="password"
                            id="passcode"
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                            placeholder="••••••••"
                            value={passcode}
                            onChange={(e) => setPasscode(e.target.value)}
                        />
                    </div>

                    {error && (
                        <div className="text-sm text-red-500 text-center">
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        className="w-full bg-blue-600 text-white font-semibold py-2 rounded-lg hover:bg-blue-700 transition-colors"
                    >
                        Access Dashboard
                    </button>
                </form>

                <div className="mt-6 text-center text-xs text-gray-400">
                    Restricted Access / Authorized Personnel Only
                </div>
            </div>
        </div>
    )
}
