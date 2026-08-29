import fs from "node:fs";
import * as E from "./engine.mjs";

const FIXED_NOW = 1750000000000;
Date.now = () => FIXED_NOW;

const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = { derive: [], score: [], picks: [], gaps: [], violates: [] };

for (const a of cases.derive) out.derive.push(E.derive(a));

for (const c of cases.wardrobes) {
  const { items, ctx } = c;
  const b = E.build(items, ctx, 0);
  out.score.push(b.map((o) => ({
    ids: o.parts.map((p) => p.id),
    total: o.score.total,
    sub: o.score.sub,
  })));
  const tp = E.topPicks(items, ctx);
  out.picks.push({
    relaxed: tp.relaxed,
    total: tp.total,
    picks: tp.picks.map((p) => ({ ids: p.parts.map((x) => x.id), total: p.score.total })),
  });
  out.gaps.push(E.analyseGaps(items, ctx));
}

for (const v of cases.violates) out.violates.push(E.violates(v.parts, v.ctx, v.level));

fs.writeFileSync(process.argv[3], JSON.stringify(out));
