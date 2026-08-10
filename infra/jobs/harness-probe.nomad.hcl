# SPDX-License-Identifier: Apache-2.0
#
# Proves the whole chain in one allocation, and doubles as the reference for
# what the Python harness will do:
#
#   Nomad workload identity -> Vault JWT auth -> dynamic Postgres credential
#     -> a connection Postgres itself expires
#
# READ THE JOBSPEC FOR WHAT ISN'T HERE: no password, no DSN, no token, no
# mounted secret. The only thing this job is given is proof of who it is.

job "harness" {
  type = "batch"

  group "probe" {
    task "probe" {
      driver = "docker"

      # The attestation. Nomad signs this; Vault verifies it against Nomad's
      # JWKS. `aud` must match the Vault role's bound_audiences, and the job ID
      # must match its bound_claims — otherwise any workload could assume the
      # harness role and the identity check would be decorative.
      identity {
        name = "vault"
        aud  = ["vault.io"]
        env  = true
        file = true
      }

      config {
        labels = {
          "com.docker.compose.project" = "brieve-local"
          "com.docker.compose.service"  = "harness"
        }

        image      = "postgres:17-alpine"
        entrypoint = ["/bin/sh", "-c"]
        args = [<<-EOS
          set -e
          apk add --no-cache curl jq > /dev/null 2>&1

          VAULT="http://host.docker.internal:8200"

          echo "1. exchanging workload identity for a Vault token"
          VT=$(curl -s -X POST "$VAULT/v1/auth/nomad/login" \
                 --data "{\"role\":\"harness\",\"jwt\":\"$NOMAD_TOKEN_vault\"}" \
               | jq -r .auth.client_token)
          test "$VT" != "null" || { echo "   FAILED: no token"; exit 1; }
          echo "   ok - token ttl $(curl -s -H "X-Vault-Token: $VT" \
                 "$VAULT/v1/auth/token/lookup-self" | jq -r .data.ttl)s"

          echo "2. reading a dynamic Postgres credential"
          C=$(curl -s -H "X-Vault-Token: $VT" "$VAULT/v1/database/creds/harness")
          PGUSER=$(echo "$C" | jq -r .data.username)
          PGPASSWORD=$(echo "$C" | jq -r .data.password)
          export PGUSER PGPASSWORD
          test "$PGUSER" != "null" || { echo "   FAILED: no credential"; exit 1; }
          echo "   ok - lease $(echo "$C" | jq -r .lease_duration)s, user $PGUSER"

          echo "3. connecting to Postgres with it"
          psql -h host.docker.internal -p 5432 -d brieve -tAc \
            "select 'connected as ' || current_user;"

          echo "4. writing and reading back, to prove it is not read-only"
          psql -h host.docker.internal -p 5432 -d brieve -q -c \
            "create table if not exists probe (at timestamptz default now());"
          psql -h host.docker.internal -p 5432 -d brieve -q -c "insert into probe default values;"
          echo "   rows in probe: $(psql -h host.docker.internal -p 5432 -d brieve -tAc 'select count(*) from probe;')"

          echo "CHAIN PROVEN - no credential was placed in this jobspec"
        EOS
        ]
      }

      resources {
        cores  = 1
        memory = 256
      }
    }
  }
}
