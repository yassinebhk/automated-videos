// Helper para actualizar un GitHub Secret vía API.
// Requiere cifrar el valor con libsodium sealed_box usando la public key del repo.
// PAT del env GITHUB_DISPATCH_TOKEN debe tener scope `secrets:write` (fine-grained)
// o `repo` completo (classic).

import sodium from "libsodium-wrappers";

/**
 * Actualiza un secret del repo.
 * @param {object} opts
 * @param {string} opts.owner   - dueño del repo (yassinebhk)
 * @param {string} opts.repo    - nombre del repo (automated-videos)
 * @param {string} opts.secretName - nombre del secret (YT_REFRESH_TOKEN)
 * @param {string} opts.value   - valor plano a cifrar
 * @param {string} opts.token   - GitHub PAT con scope secrets:write
 */
export async function updateRepoSecret({ owner, repo, secretName, value, token }) {
  await sodium.ready;

  // 1) Fetch public key del repo (para cifrar el secret)
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

  // 2) Cifrar con sealed_box
  const publicKeyBytes = sodium.from_base64(key, sodium.base64_variants.ORIGINAL);
  const valueBytes = sodium.from_string(value);
  const encryptedBytes = sodium.crypto_box_seal(valueBytes, publicKeyBytes);
  const encryptedB64 = sodium.to_base64(encryptedBytes, sodium.base64_variants.ORIGINAL);

  // 3) PUT del secret
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
