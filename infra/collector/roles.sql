-- SPDX-License-Identifier: Apache-2.0
--
-- The credential the platform holds at the destination — INSERT and SELECT, nothing else.
--
-- **This file lives outside the trust-fabric module on purpose.** Every other role in this
-- repository is defined in `infra/modules/trust-fabric/`, because every other role governs
-- something the platform administers. This one governs the platform's access to a store it
-- deliberately does NOT administer, and platform Terraform defining it would blur exactly
-- the line ADR-0055 draws. It is applied by whoever runs the collector; `enclave-up` plays
-- that part in dev, and the fact that one operator wears both hats locally is a limitation
-- of the dev enclave rather than of the design.
--
-- **Not minted by the PLATFORM's Vault's database engine seeded with the collector's root**,
-- because seeding that root would hand the platform's administrators the destination's
-- credential lifecycle — the party being guarded against holding the keys to the guard.
--
-- **That is not an argument for a hand-written password, which is what this is, and it
-- should not stay one.** Vault Enterprise 1.18+ supports rootless static roles
-- (`self_managed=true` on the connection, `self_managed_password` on the role): Vault
-- connects AS this account and rotates its own password on a `rotation_period`, holding no
-- privileged account here and gaining nothing beyond the two grants below. The enclave
-- already runs vault-enterprise 2.0.3-ent. Onboarding this role that way removes the
-- standing credential without giving the platform an inch more reach — see ADR-0055's
-- Correction and ROADMAP gap 0b.
--
-- Worth being precise about why that is safe: the boundary this file draws rests on the
-- GRANT LIST, never on who knows the password. An administrator holding this password gains
-- exactly what the platform already legitimately has, and `probe()` goes on demonstrating
-- that UPDATE and DELETE are refused.
--
-- What bounds it is this grant list. The platform can append and read; it cannot UPDATE,
-- DELETE, or TRUNCATE. `probe()` in `core/audit/destination_postgres.py` demonstrates the
-- refusal on every reconcile pass rather than trusting this file to still say what it says.

-- Idempotent: bring-up re-runs, and a role that already exists is not an error.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'harness_shipper') THEN
        CREATE ROLE harness_shipper LOGIN PASSWORD 'dev-only-shipper';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE collector TO harness_shipper;
GRANT USAGE ON SCHEMA public TO harness_shipper;

-- The whole capability, stated positively so the absences are visible by contrast.
GRANT INSERT, SELECT ON shipped_entries TO harness_shipper;
GRANT INSERT, SELECT ON shipped_head_observations TO harness_shipper;

-- Belt and braces. The grants above confer nothing else, and the role inherits nothing —
-- but the withholding is what this feature IS, so it is stated rather than implied. The
-- same reasoning the evidence role's REVOKEs in `database.tf` already carry.
REVOKE UPDATE, DELETE, TRUNCATE ON shipped_entries FROM harness_shipper;
REVOKE UPDATE, DELETE, TRUNCATE ON shipped_head_observations FROM harness_shipper;

-- No default privileges for future tables. A table added later must be granted
-- deliberately, so a new destination table cannot arrive pre-writable — the convenience
-- that would quietly undo the narrowness above.
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM harness_shipper;
