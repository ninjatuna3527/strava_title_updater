const titles = [
  "My Legs Filed a Complaint",
  "Blamed It on the Headwind",
  "Recovery Pace, Emotionally",
  "GPS Added the Slow Bits",
  "Carbs Were Still Loading",
  "Training for a Longer Nap",
  "The Hill Started It",
  "Saving My Speed for Next Time",
  "Shoelaces Were Holding Me Back",
  "Aerodynamic in Theory",
  "Tapering Since Breakfast",
  "The Route Looked Flatter Online"
];

const sampleTitle = document.querySelector("#sample-title");
const shuffleButton = document.querySelector("#shuffle");
const year = document.querySelector("#year");

year.textContent = new Date().getFullYear();

shuffleButton.addEventListener("click", () => {
  const next = titles[Math.floor(Math.random() * titles.length)];
  sampleTitle.textContent = next;
});
