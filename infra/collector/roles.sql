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
-- **Not minted by the PLATFORM's Vault**, because a credential the platform's secrets engine
-- issues is one the platform's administrators govern — the party being guarded against would
-- hold the keys to the guard.
--
-- **That is not an argument against dynamic credentials, only against dynamic credentials
-- minted here.** The right shape is a secrets store the COLLECTOR's administrators own,
-- registered against this database and federating on Nomad's JWKS — the same verifiable
-- issuer the platform's Vault already trusts. The mcp service would present the workload
-- identity it already carries and receive a leased credential, with lifecycle control
-- provably on this side of the line. The dev enclave runs a single Vault, so it cannot host
-- that separation: the platform's root token administers all of it. The standing credential
-- below is an artifact of that substrate and should not survive a real deployment.
--
-- Rotation, meanwhile, does not need a human even now. Whoever runs the collector can rotate
-- this password on a schedule and write the new value to the KV path the platform reads; the
-- platform stores the credential and does not own its lifecycle. Bring-up simply does not
-- automate it yet.
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
