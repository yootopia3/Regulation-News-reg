import { randomBytes, scrypt as derive, timingSafeEqual } from 'node:crypto'

function scrypt(password: string, salt: string): Promise<Buffer> {
    return new Promise((resolve, reject) => derive(password, salt, 64, { N: 16384, r: 8, p: 1, maxmem: 64 * 1024 * 1024 }, (error, result) => error ? reject(error) : resolve(result)))
}
export async function hashBoardPassword(password: string) {
    const salt = randomBytes(16).toString('hex')
    return `scrypt-v1$${salt}$${(await scrypt(password, salt)).toString('hex')}`
}
export async function verifyBoardPassword(password: string, hash: string) {
    const match = /^scrypt-v1\$([a-f0-9]{32})\$([a-f0-9]{128})$/.exec(hash)
    if (!match || password.length < 8 || password.length > 128) return false
    return timingSafeEqual(await scrypt(password, match[1]), Buffer.from(match[2], 'hex'))
}
