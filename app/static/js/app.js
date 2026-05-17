const countsUrl = "/notifications/counts";
const searchUrl = "/listings/api/search";

function updateBadgeCounts() {
  if (document.body.dataset.authenticated !== "true") {
    return;
  }
  fetch(countsUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } })
    .then((response) => response.ok ? response.json() : null)
    .then((data) => {
      if (!data) return;
      document.querySelectorAll(".nav-count").forEach((badge) => {
        const type = badge.dataset.countType;
        const value = data[type] ?? 0;
        badge.textContent = value;
        badge.classList.toggle("d-none", value === 0);
      });
    })
    .catch(() => {});
}

function wireLiveSearch() {
  const form = document.querySelector("#searchForm[data-live-search='true']");
  const resultsContainer = document.getElementById("listingResults");
  const resultCount = document.getElementById("resultCount");
  if (!form || !resultsContainer || !resultCount) {
    return;
  }

  let timeoutHandle = null;
  const runSearch = () => {
    const params = new URLSearchParams(new FormData(form));
    fetch(`${searchUrl}?${params.toString()}`)
      .then((response) => response.ok ? response.json() : null)
      .then((data) => {
        if (!data) return;
        resultCount.textContent = data.count;
        resultsContainer.innerHTML = data.html;
      })
      .catch(() => {});
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    runSearch();
  });

  form.querySelectorAll("input, select").forEach((field) => {
    field.addEventListener("input", () => {
      window.clearTimeout(timeoutHandle);
      timeoutHandle = window.setTimeout(runSearch, 250);
    });
    field.addEventListener("change", () => {
      window.clearTimeout(timeoutHandle);
      timeoutHandle = window.setTimeout(runSearch, 100);
    });
  });
}

updateBadgeCounts();
wireLiveSearch();
window.setInterval(updateBadgeCounts, 30000);
