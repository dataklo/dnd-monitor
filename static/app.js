const grid = document.getElementById("grid");
let latestPhones = [];
const CLICK_COOLDOWN_MS = 5000;
const cooldownUntil = new Map();
const READ_ONLY_MODE = window.DND_MONITOR_READONLY === true;

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

    const nameNode = tile.querySelector(".name");
    if (nameNode && !READ_ONLY_MODE) {
      nameNode.style.cursor = "pointer";
      nameNode.title = "Klicken: DND am Telefon auslösen";

      const trigger = async () => {
        const confirmed = window.confirm(`DND für ${phone.display_name} wirklich toggeln?`);
        if (!confirmed) {
          return;
        }

        const now = Date.now();
        const blockedUntil = cooldownUntil.get(phone.mac) || 0;
        if (now < blockedUntil) {
          const remainingSeconds = Math.ceil((blockedUntil - now) / 1000);
          alert(`Bitte ${remainingSeconds}s warten (Cooldown).`);
          return;
        }

        cooldownUntil.set(phone.mac, now + CLICK_COOLDOWN_MS);

        try {
          const response = await fetch(`/api/phones/${encodeURIComponent(phone.mac)}/dnd`, {
            method: "POST",
          });
          if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            const errorMessage = payload.detail || payload.error || `HTTP ${response.status}`;
            alert(`Webhook fehlgeschlagen für ${phone.display_name}: ${errorMessage}`);
          }
        } catch (error) {
          alert(`Webhook fehlgeschlagen für ${phone.display_name}: ${String(error)}`);
        }
      };

      nameNode.addEventListener("click", trigger);
    }

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
