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

function createSkillRow(fieldName, skillName) {
  const row = document.createElement("div");
  row.className = "input-group skill-row";
  row.dataset.skillRow = "";

  const input = document.createElement("input");
  input.className = "form-control";
  input.name = fieldName;
  input.type = "text";
  input.maxLength = 120;
  input.value = skillName;
  input.setAttribute("aria-label", "Profile skill");

  const button = document.createElement("button");
  button.className = "btn btn-outline-danger";
  button.type = "button";
  button.dataset.removeSkill = "";
  button.textContent = "Remove";

  row.append(input, button);
  return row;
}

function updateSkillEmptyState(editor) {
  const emptyState = editor.querySelector("[data-empty-skills]");
  const list = editor.querySelector("[data-skill-list]");
  if (!emptyState || !list) {
    return;
  }
  emptyState.classList.toggle("d-none", list.querySelectorAll("[data-skill-row]").length > 0);
}

function wireProfileEditForm() {
  const form = document.querySelector("[data-profile-edit-form]");
  if (!form) {
    return;
  }

  let isDirty = false;
  let submitted = false;
  const markDirty = () => {
    if (!submitted) {
      isDirty = true;
    }
  };

  form.addEventListener("input", markDirty);
  form.addEventListener("change", markDirty);
  form.addEventListener("submit", () => {
    submitted = true;
    isDirty = false;
  });

  const unsavedModal = document.querySelector("[data-unsaved-modal]");
  const leaveButton = unsavedModal ? unsavedModal.querySelector("[data-leave-profile]") : null;
  let pendingNavigationUrl = null;

  function getUnsavedModalInstance() {
    if (!unsavedModal || !window.bootstrap || !window.bootstrap.Modal) {
      return null;
    }
    return window.bootstrap.Modal.getOrCreateInstance(unsavedModal);
  }

  function showUnsavedModal(url) {
    pendingNavigationUrl = url;
    const modalInstance = getUnsavedModalInstance();
    if (modalInstance) {
      modalInstance.show();
      return;
    }
    unsavedModal.classList.add("show");
    unsavedModal.style.display = "block";
    unsavedModal.removeAttribute("aria-hidden");
  }

  function hideUnsavedModal() {
    const modalInstance = getUnsavedModalInstance();
    if (modalInstance) {
      modalInstance.hide();
      return;
    }
    unsavedModal.classList.remove("show");
    unsavedModal.style.display = "none";
    unsavedModal.setAttribute("aria-hidden", "true");
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element) || !isDirty || submitted || !unsavedModal) {
      return;
    }
    const link = target.closest("a[href]");
    if (!link || link.closest("[data-unsaved-modal]") || link.target === "_blank") {
      return;
    }
    event.preventDefault();
    showUnsavedModal(link.href);
  });

  if (unsavedModal) {
    unsavedModal.querySelectorAll("[data-stay-on-profile]").forEach((button) => {
      button.addEventListener("click", () => {
        pendingNavigationUrl = null;
        hideUnsavedModal();
      });
    });
  }

  if (leaveButton) {
    leaveButton.addEventListener("click", () => {
      if (!pendingNavigationUrl) {
        hideUnsavedModal();
        return;
      }
      submitted = true;
      isDirty = false;
      window.location.href = pendingNavigationUrl;
    });
  }

  window.addEventListener("beforeunload", (event) => {
    if (!isDirty || submitted) {
      return;
    }
    event.preventDefault();
    event.returnValue = "";
  });

  form.querySelectorAll("[data-skill-editor]").forEach((editor) => {
    editor.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }

      const addButton = target.closest("[data-add-skill]");
      if (addButton) {
        const input = editor.querySelector("[data-new-skill]");
        const list = editor.querySelector("[data-skill-list]");
        const skillName = input ? input.value.trim().replace(/\s+/g, " ") : "";
        if (!skillName || !list) {
          return;
        }
        list.append(createSkillRow(editor.dataset.skillField, skillName));
        input.value = "";
        updateSkillEmptyState(editor);
        markDirty();
        return;
      }

      const removeButton = target.closest("[data-remove-skill]");
      if (removeButton) {
        const row = removeButton.closest("[data-skill-row]");
        if (row) {
          row.remove();
          updateSkillEmptyState(editor);
          markDirty();
        }
      }
    });
    updateSkillEmptyState(editor);
  });

  const avatarInput = form.querySelector("[data-avatar-input]");
  const preview = form.querySelector("[data-avatar-preview]");
  const placeholder = form.querySelector("[data-avatar-placeholder]");
  const error = form.querySelector("[data-avatar-error]");
  let previewUrl = null;

  if (avatarInput && preview) {
    avatarInput.addEventListener("change", () => {
      const file = avatarInput.files && avatarInput.files[0];
      if (!file) {
        return;
      }

      if (!["image/jpeg", "image/png"].includes(file.type) || file.size > 5 * 1024 * 1024) {
        avatarInput.classList.add("is-invalid");
        if (error) {
          error.textContent = "Choose a JPG or PNG avatar under 5MB.";
          error.classList.add("d-block");
        }
        avatarInput.value = "";
        return;
      }

      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      previewUrl = URL.createObjectURL(file);
      preview.src = previewUrl;
      preview.classList.remove("d-none");
      if (placeholder) {
        placeholder.classList.add("d-none");
      }
      avatarInput.classList.remove("is-invalid");
      if (error) {
        error.textContent = "";
        error.classList.remove("d-block");
      }
    });
  }
}

updateBadgeCounts();
wireLiveSearch();
wireProfileEditForm();
window.setInterval(updateBadgeCounts, 30000);
