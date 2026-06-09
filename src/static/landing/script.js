const titles = [
  "雲中疾行",
  "夜雨疾馳",
  "山風未息",
  "孤月長跑",
  "晨霧破風",
  "龍脈上升",
  "竹影慢行",
  "雲海歸途",
  "赤日遠征",
  "寒星踏步",
  "松下疾影",
  "白鶴越嶺",
  "雨後登峰",
  "火雲追風"
];

const sampleTitle = document.querySelector("#sample-title");
const shuffleButton = document.querySelector("#shuffle");
const year = document.querySelector("#year");

year.textContent = new Date().getFullYear();

shuffleButton.addEventListener("click", () => {
  const next = titles[Math.floor(Math.random() * titles.length)];
  sampleTitle.textContent = next;
});
