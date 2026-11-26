// Timeline única do vídeo. T (instantes das palavras) e C (cortes) vêm do gen.py.
const tl = gsap.timeline({ paused: true });

// ---------- helpers de revelação
function rise(sel, t, dy = 70, d = 0.45) { tl.set(sel, { opacity: 1, y: dy }, t); tl.to(sel, { y: 0, duration: d, ease: "power4.out" }, t); }
function pop(sel, t) { tl.set(sel, { opacity: 1, scale: 1.25 }, t); tl.to(sel, { scale: 1, duration: 0.4, ease: "back.out(1.6)" }, t); }
function fromLeft(sel, t) { tl.fromTo(sel, { opacity: 0, x: 120 }, { opacity: 1, x: 0, duration: 0.45, ease: "power4.out", immediateRender: false }, t); }
function words(c, t, total) {
  const ws = [...document.querySelectorAll(c + " .w")], g = Math.min(0.16, total / ws.length);
  ws.forEach((el, i) => { tl.set(el, { opacity: 1, y: 70 }, t + i * g); tl.to(el, { y: 0, duration: 0.32, ease: "power4.out" }, t + i * g); });
}
function counter(sel, a, b, t, d, fmt) {
  const el = document.querySelector(sel), o = { v: a };
  const f = fmt || (v => String(Math.round(v)));
  el.textContent = f(a);
  tl.fromTo(o, { v: a }, { v: b, duration: d, ease: "power2.out", onUpdate: () => (el.textContent = f(o.v)) }, t);
}
const milhar = v => Math.round(v).toLocaleString("pt-BR");

// ---------- transições (corrente única para a esquerda; zoom só no clímax; subida só na conclusão)
let gx = 0;
function seamLeft(a, b, Cc) {
  tl.to("#w" + a, { x: -230, filter: "blur(8px)", duration: 0.33, ease: "power4.in" }, Cc - 0.33);
  tl.to("#w" + a, { opacity: 0, duration: 0.31, ease: "power2.in" }, Cc - 0.32);
  tl.fromTo("#w" + b, { x: 230, opacity: 0.35, filter: "blur(8px)" },
    { x: 0, opacity: 1, filter: "blur(0px)", duration: 0.42, ease: "power4.out", immediateRender: false }, Cc);
  gx -= 90; tl.to("#grid", { x: gx, duration: 0.75, ease: "power4.inOut" }, Cc - 0.33);
}
function seamZoom(a, b, Cc) {
  tl.to("#w" + a, { scale: 1.2, filter: "blur(10px)", duration: 0.2, ease: "power3.in" }, Cc - 0.2);
  tl.to("#w" + a, { opacity: 0.15, duration: 0.2, ease: "none" }, Cc - 0.2);
  tl.fromTo("#w" + b, { scale: 0.75, opacity: 0.15, filter: "blur(10px)" },
    { scale: 1, opacity: 1, filter: "blur(0px)", duration: 0.5, ease: "expo.out", immediateRender: false }, Cc);
}
function seamUp(a, b, Cc) {
  tl.to("#w" + a, { y: -400, filter: "blur(8px)", duration: 0.33, ease: "power4.in" }, Cc - 0.33);
  tl.to("#w" + a, { opacity: 0, duration: 0.31, ease: "power2.in" }, Cc - 0.32);
  tl.fromTo("#w" + b, { y: 400, opacity: 0.35, filter: "blur(8px)" },
    { y: 0, opacity: 1, filter: "blur(0px)", duration: 0.42, ease: "power4.out", immediateRender: false }, Cc);
  tl.to("#grid", { y: -90, duration: 0.75, ease: "power4.inOut" }, Cc - 0.33);
}

// ---------- progresso
tl.fromTo("#prog", { scaleX: 0, transformOrigin: "0 50%" }, { scaleX: 1, duration: DUR, ease: "none" }, 0);

// ---------- s1 gancho: creators sacando; alguns pontos viram fraude
rise("#s1l", 0.3, 40);
for (let i = 0; i < 48; i++) {
  const ti = T.s1_dots + i * 0.075;
  tl.set("#d" + i, { opacity: 1, scale: 0.4 }, ti);
  tl.to("#d" + i, { scale: 1, backgroundColor: "#8CD43A", duration: 0.35, ease: "power4.out" }, ti);
}
FRAUDE_DOTS.forEach((k, j) => tl.to("#d" + k, { backgroundColor: "#E5524C", scale: 1.15, duration: 0.3, ease: "power4.out" }, T.fraude1 + j * 0.05));
pop("#s1f", T.fraude1);

// ---------- s2 problema
seamLeft(1, 2, C[1]);
rise("#c2", C[1] + 0.1, 30);
fromLeft("#t1", T.auto); fromLeft("#t2", T.cartao); fromLeft("#t3", T.pix);
rise("#s2din", T.saiu - 0.9);
tl.to("#s2din", { x: 1100, opacity: 0, duration: 0.6, ease: "power3.in" }, T.saiu);
pop("#s2p", T.prejuizo - 0.4);

// ---------- s3 solução
seamLeft(2, 3, C[2]);
rise("#c3", C[2] + 0.1, 30);
pop("#s3logo", T.eu);
rise("#s3n", T.sent - 0.1);
rise("#s3a", T.analisa);
rise("#s3b", T.bloqueia - 0.5);
rise("#s3c", T.retem - 0.1);
tl.fromTo("#s3c .badge", { scale: 1.4 }, { scale: 1, duration: 0.4, ease: "back.out(1.6)" }, T.retem);
rise("#s3d", T.retem + 0.8);

// ---------- s4 como funciona
seamLeft(3, 4, C[3]);
rise("#c4", C[3] + 0.1, 30);
rise("#s4t", T.camadas - 0.6);
rise("#k1", T.sete); rise("#k2", T.lgbm); rise("#k3", T.agente);
rise("#s4ok", T.conferido);

// ---------- s5 telas reais (troca interna também para a esquerda)
seamLeft(4, 5, C[4]);
rise("#c5", C[4] + 0.1, 30);
const telas = [["#v1", "#l1", T.fila - 0.3], ["#v2", "#l2", T.provas - 0.2], ["#v3", "#l3", T.mapa - 0.4], ["#v4", "#l4", T.decisao - 0.2]];
telas.forEach(([v, l, ti], i) => {
  if (i > 0) {
    const [pv, pl] = telas[i - 1];
    tl.to([pv, pl], { x: -260, opacity: 0, duration: 0.33, ease: "power4.in" }, ti - 0.33);
  }
  tl.fromTo(v, { x: 260, opacity: 0 }, { x: 0, opacity: 1, duration: 0.45, ease: "power4.out", immediateRender: false }, ti);
  tl.fromTo(l, { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.35, ease: "power4.out", immediateRender: false }, ti + 0.15);
  // nada parado: a tela segue avançando devagar enquanto é explicada
  const fim = i + 1 < telas.length ? telas[i + 1][2] - 0.33 : C[5] - 0.33;
  tl.to(v, { y: -24, duration: Math.max(0.5, fim - ti - 0.45), ease: "none" }, ti + 0.45);
});

// ---------- s6 bastidores
seamLeft(5, 6, C[5]);
rise("#c6", C[5] + 0.1, 30);
rise("#s6t", T.apr);
rise("#a1", T.formula);
counter("#n51", 51, 51, T.p51, 0.1);
tl.to("#a1 .v", { color: "#E5524C", duration: 0.2 }, T.p51);
counter("#n51", 51, 85, T.recal, 1.2);
tl.to("#a1 .v", { color: "#8CD43A", duration: 0.4 }, T.recal);
rise("#a2", T.modelo);
tl.to("#rp", { "--s": 1, color: "#A7B4C9", duration: 0.35, ease: "power3.out" }, T.prompt + 0.6);
pop("#cod", T.codigo);
rise("#a3", T.claros - 0.3);
tl.fromTo("#b52", { width: "100%" }, { width: "48%", duration: 1.0, ease: "power3.inOut" }, T.p52 - 0.4);
pop("#m52", T.p52);

// ---------- s7 resultados
seamLeft(6, 7, C[6]);
rise("#c7", C[6] + 0.1, 30);
rise("#s7b", T.base - 0.5, 30);
counter("#n1158", 0, 1158, T.base - 0.3, 1.0, milhar);
rise("#r1", T.p85 - 0.2); counter("#n85", 0, 85, T.p85 - 0.2, 0.9);
rise("#r2", T.p94 - 0.2); counter("#n94", 0, 94, T.p94 - 0.2, 0.9);
rise("#r3", T.trinta - 0.2);
rise("#r4", T.mil16 - 0.5);
tl.to("#bf", { width: "100%", duration: 0.9, ease: "power3.out" }, T.mil16);
rise("#r5l", T.r143 - 0.4, 30); rise("#r5t", T.r143 - 0.4, 30);
tl.to("#bl", { width: "0.9%", duration: 0.6, ease: "power3.out" }, T.r143);

// ---------- s8 antes do clímax (pausa de quietude antes do impacto)
seamLeft(7, 8, C[7]);
words("#s8a", T.mas, 1.4);
rise("#s8b", T.seguida, 40);

// ---------- s9 clímax: o 7
seamZoom(8, 9, C[8]);
tl.set("#s9n", { opacity: 1 }, C[8]);
rise("#s9a", T.fraudadores, 40);
rise("#s9b", T.recomenda, 40);
rise("#s9c", T.quem, 40);
tl.fromTo("#s9c .lime", { opacity: 0.3 }, { opacity: 1, duration: 0.3 }, T.pessoa);

// ---------- s10 assinatura (subida: conclusão)
seamUp(9, 10, C[9]);
pop("#s10logo", T.sent2 - 0.1);
rise("#s10n", T.sent2);
rise("#s10p", T.protecao, 40);
tl.to("#s10tr", { width: 260, duration: 0.6, ease: "power4.out" }, T.caio - 0.4);
rise("#s10c", T.caio, 40);
rise("#s10s", T.caio - 0.2, 30);
