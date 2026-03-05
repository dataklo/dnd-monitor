const grid = document.getElementById("grid");
let latestPhones = [];

function getColumnCount() {
  if (window.matchMedia("(max-width: 500px)").matches) {
    return 1;
  }
  if (window.matchMedia("(max-width: 900px)").matches) {
    return 2;
  }
  return 4;
}

function render(phones = latestPhones) {
  latestPhones = phones;
  if (!phones.length) {
    grid.style.removeProperty("--rows");
    grid.innerHTML = "<p>Noch keine Telefone gemeldet.</p>";
    return;
  }

  const columns = getColumnCount();
  const rows = Math.ceil(phones.length / columns);
  grid.style.setProperty("--rows", String(rows));

  grid.innerHTML = "";
  for (const phone of phones) {
    const tile = document.createElement("article");
    tile.className = `tile ${phone.status}`;

    tile.innerHTML = `<div class="name">${phone.display_name}</div>`;

    grid.appendChild(tile);
  }
}

async function refresh() {
  const response = await fetch("/api/phones", { cache: "no-store" });
  const payload = await response.json();
  render(payload.phones || []);
}

window.addEventListener("resize", () => render());
refresh();
setInterval(refresh, 3000);
