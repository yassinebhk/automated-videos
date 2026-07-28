// Helper para actualizar un GitHub Secret vía API.
// GitHub cifra los secrets con sealed_box de libsodium (X25519 + XSalsa20-Poly1305).
// libsodium-wrappers ESM está roto en Vercel (module not found libsodium.mjs), así que
// implementamos sealed_box manualmente con tweetnacl + @noble/hashes/blake2b —
// ambos JS puros, sin deps nativas, funcionan en cualquier entorno serverless.
//
// PAT del env GITHUB_DISPATCH_TOKEN debe tener scope `secrets:write` (fine-grained)
// o `repo` completo (classic).

import nacl from "tweetnacl";
import { blake2b } from "@noble/hashes/blake2b";

/**
 * sealed_box(m, pk) implementación conforme a libsodium.
 *
 *   ephemeral_pk || box(m, nonce=blake2b(ephemeral_pk||pk, 24), pk, ephemeral_sk)
 *
 * Devuelve Uint8Array de longitud 32 + len(m) + 16.
 */
function sealedBox(message, recipientPubKey) {
  const ek = nacl.box.keyPair(); // ephemeral X25519 keypair
  const nonceInput = new Uint8Array(64);
  nonceInput.set(ek.publicKey, 0);
  nonceInput.set(recipientPubKey, 32);
  const nonce = blake2b(nonceInput, { dkLen: 24 });

  const ciphertext = nacl.box(message, nonce, recipientPubKey, ek.secretKey);

  const sealed = new Uint8Array(32 + ciphertext.length);
  sealed.set(ek.publicKey, 0);
  sealed.set(ciphertext, 32);
  return sealed;
}

function b64encode(bytes) {
  return Buffer.from(bytes).toString("base64");
}

function b64decode(str) {
  return new Uint8Array(Buffer.from(str, "base64"));
}

/**
 * Actualiza un secret del repo.
 * @param {object} opts
 * @param {string} opts.owner
 * @param {string} opts.repo
 * @param {string} opts.secretName
 * @param {string} opts.value
 * @param {string} opts.token   - PAT GitHub con scope secrets:write
 */
export async function updateRepoSecret({ owner, repo, secretName, value, token }) {
  // 1) Public key del repo
  const pkResp = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/actions/secrets/public-key`,
    {
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2022-11-28",
      },
    }
  );
  if (!pkResp.ok) {
    const t = await pkResp.text();
    throw new Error(`GitHub public-key fetch failed (${pkResp.status}): ${t.slice(0, 200)}`);
  }
  const { key, key_id } = await pkResp.json();

  // 2) Cifrar
  const publicKeyBytes = b64decode(key);
  const valueBytes = new TextEncoder().encode(value);
  const sealed = sealedBox(valueBytes, publicKeyBytes);
  const encryptedB64 = b64encode(sealed);

  // 3) PUT
  const putResp = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/actions/secrets/${secretName}`,
    {
      method: "PUT",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ encrypted_value: encryptedB64, key_id }),
    }
  );
  if (!putResp.ok && putResp.status !== 204) {
    const t = await putResp.text();
    throw new Error(`GitHub secret update failed (${putResp.status}): ${t.slice(0, 200)}`);
  }
  return true;
}
