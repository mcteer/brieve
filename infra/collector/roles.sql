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
-- **Not Vault-minted, and that is the argument rather than an omission.** Dynamic
-- credentials would be more convenient to rotate and would hand the platform's Vault — and
-- therefore the platform's administrators — control of the destination's credential
-- lifecycle. The party being guarded against would hold the keys to the guard. So this is a
-- standing credential, named and bounded, on the same footing ADR-0044 gave the TFE
-- management token: argued in the plan's Complexity Tracking, not smuggled in.
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
