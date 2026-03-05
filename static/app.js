const grid = document.getElementById("grid");

function render(phones) {
  if (!phones.length) {
    grid.innerHTML = "<p>Noch keine Telefone gemeldet.</p>";
    return;
  }

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

refresh();
setInterval(refresh, 3000);
