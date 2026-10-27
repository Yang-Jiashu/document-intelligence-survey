# RRC TLS intermediate

`harica-geant-tls-r1.pem` is the public GEANT TLS RSA 1 intermediate issued by HARICA TLS RSA Root CA 2021. It was retrieved on 2026-10-27 from the CA Issuers URL advertised by the RRC server certificate:

http://crt.harica.gr/HARICA-GEANT-TLS-R1.cer

DER SHA-256: `5b678dc44095a52895b63b31f27227f4b36c3e347491bf2bfa691837a5fb8c79`.

Intermediate validity: 2025-01-03 through 2039-12-31.

The RRC server presented only its leaf certificate to GitHub-hosted runners, causing `unable to get local issuer certificate` with both Python's default and Ubuntu's system CA bundle. Supplying this missing intermediate allowed the captured leaf to verify against the existing system roots, including hostname `rrc.cvc.uab.es`.

The RRC adapter augments the default verification context with this intermediate. It requires a complete chain to an existing trusted root (partial-chain trust is disabled) and continues to verify certificate validity and hostname. It does not install a new root, trust the leaf, or disable verification. TLS errors still do not trigger HTTP fallback. A future correctly configured server can supply its own intermediates normally.
