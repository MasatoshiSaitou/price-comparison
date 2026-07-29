// オフラインモード用: サーバー/インターネット接続なしで動作する簡易類似度検索。
//
// Sentence Transformers のような埋め込みモデルはスマホ単体では非現実的
// （重すぎる、Expo Goでは動かせない）ため、文字bi-gramのDice係数で
// 簡易的な類似度を計算する。日本語は単語間にスペースがないため、
// 単語分割ではなく文字単位のn-gramを使うのが実用的。

function toBigrams(text) {
  const normalized = (text || '').replace(/\s+/g, '');
  const grams = new Set();
  for (let i = 0; i < normalized.length - 1; i++) {
    grams.add(normalized.slice(i, i + 2));
  }
  return grams;
}

function diceCoefficient(bigramsA, bigramsB) {
  if (bigramsA.size === 0 || bigramsB.size === 0) return 0;
  let intersection = 0;
  for (const gram of bigramsA) {
    if (bigramsB.has(gram)) intersection++;
  }
  return (2 * intersection) / (bigramsA.size + bigramsB.size);
}

export function searchOfflineIncidents(query, incidents, topK = 5) {
  const queryBigrams = toBigrams(query);
  const scored = incidents.map((incident) => ({
    incident,
    score: diceCoefficient(
      queryBigrams,
      toBigrams(`${incident.work_type} ${incident.description}`)
    ),
  }));
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, topK).map((s) => s.incident);
}

export function buildOfflineBriefText(query, matches) {
  if (matches.length === 0) {
    return (
      `「${query}」に類似する過去の災害事例が見つかりませんでした。` +
      '作業前に元請・安全担当者へ確認してください。'
    );
  }
  const points = matches
    .map((m, i) => `${i + 1}. ${m.description}\n   → 対策: ${m.preventive}`)
    .join('\n\n');
  return (
    `「${query}」に類似する過去の労働災害事例と対策です。\n` +
    '（オフラインモードのため、Claudeによるその場での生成ではなく、' +
    '過去事例に登録済みの対策をそのまま表示しています）\n\n' +
    points
  );
}
