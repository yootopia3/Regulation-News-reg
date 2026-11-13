# Daily regulatory delta mail

The hosted workflow runs on business days at 09:00 Asia/Seoul. Its existing
calendar, single-writer lock, private delivery state and recipient configuration
remain authoritative. Sending a packet does not confirm its import inside the bank.

## Attachments

New deliveries first combine the daily changes using the existing REGDATA1
contract and compress them into a ZIP containing exactly one `.regdata` file.
The recipient uses Windows **Extract All**, then imports that `.regdata` through
the existing administrator page. No application image update is required.
Instructions and original-download warnings are included in the email body;
there are no separate instruction attachments.

The packer measures compressed size instead of splitting every 16 MB of raw data.
It splits by complete article only when a ZIP would exceed its email budget, or
the existing importer limits (200 records, 900 MiB and record JSON limits) require
separate packets. Every record and original file is preserved. An indivisible
oversized record stops preparation without advancing the delivery cursor.

[Gmail's personal-account attachment limit](https://support.google.com/mail/answer/6584)
is 25 MB before MIME encoding. We enforce 25,000,000 bytes of total attachments,
reserve space for body/warnings during packing, preflight the complete MIME at
35,000,000 bytes, and check the SMTP server's advertised SIZE before DATA. The
public SMTP endpoint advertised 35,882,577 bytes when verified on 2026-11-13.
One file is preferred, but cannot be guaranteed for arbitrarily large daily data.
The dedicated private Storage bucket must allow at least 25,000,000 bytes per
object (or have no bucket-specific cap). Configuration checks reject a smaller
cap before preparing or sending packets. Keep its public flag false.

## Recovery and compatibility

Already prepared raw `.regdata` packets remain readable and resume without being
repackaged. New ZIPs are read without extraction; only one bounded `.regdata` entry
is accepted. Manifest, record and file hashes are verified before delivery.
SENT verification still compares exact attachment bytes. The remote send-attempt
marker remains durable before SMTP; unknown results are not automatically resent.
No public download URL or additional email account is needed.
