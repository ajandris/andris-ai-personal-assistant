/**
 * Frontend logic for Andris Jancevskis Portfolio & AI Sales Assistant
 * Stage 3 & 4 implementation with OpenAI & FAISS RAG integration
 */

document.addEventListener("DOMContentLoaded", () => {
  initMobileNavigation();
  initSmoothScroll();
  initActiveNavHighlight();
  initAIAssistantChat();
  initDirectLeadForm();
});

/**
 * 1. Mobile navigation menu handler
 */
function initMobileNavigation() {
  const menuToggle = document.getElementById("menu-toggle");
  const navMenu = document.getElementById("primary-navigation");

  if (!menuToggle || !navMenu) return;

  function toggleMenu(forceClose = false) {
    const isExpanded = menuToggle.getAttribute("aria-expanded") === "true";
    const shouldOpen = forceClose ? false : !isExpanded;

    menuToggle.setAttribute("aria-expanded", String(shouldOpen));
    menuToggle.setAttribute(
      "aria-label",
      shouldOpen ? "Закрыть главное меню" : "Открыть главное меню"
    );

    if (shouldOpen) {
      navMenu.classList.add("is-open");
    } else {
      navMenu.classList.remove("is-open");
    }
  }

  menuToggle.addEventListener("click", () => toggleMenu());

  navMenu.querySelectorAll(".nav-link, .btn-header-ai").forEach((link) => {
    link.addEventListener("click", () => toggleMenu(true));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && navMenu.classList.contains("is-open")) {
      toggleMenu(true);
      menuToggle.focus();
    }
  });

  document.addEventListener("click", (event) => {
    if (
      navMenu.classList.contains("is-open") &&
      !navMenu.contains(event.target) &&
      !menuToggle.contains(event.target)
    ) {
      toggleMenu(true);
    }
  });
}

/**
 * 2. Smooth scrolling taking header offset and prefers-reduced-motion into account
 */
function initSmoothScroll() {
  const isReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.querySelectorAll('a[href^="#"], a[href^="/#"]').forEach((anchor) => {
    anchor.addEventListener("click", (event) => {
      const href = anchor.getAttribute("href");
      if (!href || href === "#" || href === "/#") return;

      const hashIndex = href.indexOf("#");
      if (hashIndex === -1) return;
      const targetId = href.slice(hashIndex);

      const currentPath = window.location.pathname;
      const isHomePage = currentPath === "/" || currentPath === "";
      const isAnchorOnly = href.startsWith("#");

      if (!isHomePage && !isAnchorOnly) return;

      const targetElement = document.querySelector(targetId);
      if (targetElement) {
        event.preventDefault();

        const header = document.querySelector(".site-header");
        const headerOffset = header ? header.offsetHeight + 16 : 80;
        const elementPosition = targetElement.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

        window.scrollTo({
          top: offsetPosition,
          behavior: isReducedMotion ? "auto" : "smooth",
        });

        if (targetElement.getAttribute("tabindex") === null) {
          targetElement.setAttribute("tabindex", "-1");
        }
        targetElement.focus({ preventScroll: true });

        history.pushState(null, "", targetId);
      }
    });
  });
}

/**
 * 3. Active menu item in header
 */
function initActiveNavHighlight() {
  const navLinks = Array.from(document.querySelectorAll(".site-nav .nav-link"));
  const aiButton = document.querySelector(".btn-header-ai");
  const currentPath = window.location.pathname.replace(/\/$/, "") || "/";
  const isHomePage = currentPath === "/";

  function clearActiveStates() {
    navLinks.forEach((link) => {
      link.classList.remove("active", "is-active");
      link.removeAttribute("aria-current");
    });
    if (aiButton) {
      aiButton.classList.remove("active", "is-active");
      aiButton.removeAttribute("aria-current");
    }
  }

  function setActiveLink(link, isPage = false) {
    if (!link) return;
    clearActiveStates();
    link.classList.add("active", "is-active");
    link.setAttribute("aria-current", isPage ? "page" : "location");
  }

  if (!isHomePage) {
    if (currentPath === "/experience") {
      setActiveLink(navLinks.find((l) => l.getAttribute("href") === "/experience"), true);
    } else if (currentPath === "/skills") {
      setActiveLink(navLinks.find((l) => l.getAttribute("href") === "/skills"), true);
    } else if (currentPath === "/education") {
      setActiveLink(navLinks.find((l) => l.getAttribute("href") === "/education"), true);
    } else if (currentPath === "/portfolio") {
      setActiveLink(navLinks.find((l) => l.getAttribute("href") === "/portfolio"), true);
    } else if (currentPath === "/contact" || currentPath === "/contacts") {
      setActiveLink(navLinks.find((l) => l.getAttribute("href") === "/contact" || l.getAttribute("href") === "/contacts"), true);
    } else if (currentPath === "/ai-assistant") {
      setActiveLink(aiButton, true);
    }
    return;
  }
}

/**
 * 4. Helper to render formatted Markdown safely in message bubbles
 */
function formatMarkdown(text) {
  if (!text) return "";
  let clean = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Bold **text**
  clean = clean.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  // Italic *text*
  clean = clean.replace(/\*(.*?)\*/g, "<em>$1</em>");
  // Inline code `code`
  clean = clean.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Convert markdown links [title](url)
  clean = clean.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="chat-inline-link">$1 ↗</a>');

  // Convert line breaks and bullet lists
  const lines = clean.split("\n");
  let inList = false;
  let html = "";

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith("- ") || line.startsWith("• ") || line.startsWith("* ")) {
      if (!inList) {
        html += '<ul class="chat-list">';
        inList = true;
      }
      html += `<li>${line.slice(2)}</li>`;
    } else if (/^\d+\.\s/.test(line)) {
      if (!inList) {
        html += '<ol class="chat-list">';
        inList = true;
      }
      const itemContent = line.replace(/^\d+\.\s/, "");
      html += `<li>${itemContent}</li>`;
    } else {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      if (line.length > 0) {
        html += `<p>${line}</p>`;
      }
    }
  }
  if (inList) {
    html += "</ul>";
  }

  return html;
}

/**
 * 5. AI Sales Assistant Interactive Chat with RAG
 */
function initAIAssistantChat() {
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatMessages = document.getElementById("chat-messages");
  const chipButtons = document.querySelectorAll(".chip-btn");
  const chatFeedback = document.getElementById("chat-feedback");
  const submitBtn = document.getElementById("chat-submit-btn");
  const banner = document.getElementById("lead-notification-banner");
  const bannerClose = document.getElementById("btn-close-banner");

  if (!chatForm || !chatInput || !chatMessages) return;

  // In-memory conversation history for multi-turn sales dialogue
  const conversationHistory = [];

  if (bannerClose && banner) {
    bannerClose.addEventListener("click", () => {
      banner.hidden = true;
    });
  }

  function showLeadNotification(message) {
    if (!banner) return;
    const bannerText = document.getElementById("lead-banner-text");
    if (bannerText && message) {
      bannerText.textContent = message;
    }
    banner.hidden = false;
    banner.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function appendUserMessage(text) {
    const messageDiv = document.createElement("div");
    messageDiv.classList.add("message", "message-user");

    const bubble = document.createElement("div");
    bubble.classList.add("message-bubble");
    const p = document.createElement("p");
    p.textContent = text;
    bubble.appendChild(p);

    messageDiv.appendChild(bubble);
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    conversationHistory.push({ role: "user", content: text });
  }

  function createTypingIndicator() {
    const indicatorDiv = document.createElement("div");
    indicatorDiv.classList.add("message", "message-assistant", "message-typing");
    indicatorDiv.id = "typing-indicator";

    const bubble = document.createElement("div");
    bubble.classList.add("message-bubble", "typing-bubble");
    bubble.innerHTML = `
      <div class="typing-dots" aria-label="AI Agent формирует ответ">
        <span></span><span></span><span></span>
      </div>
      <span class="typing-text">Поиск в RAG базе знаний и сопоставление навыков...</span>
    `;

    indicatorDiv.appendChild(bubble);
    chatMessages.appendChild(indicatorDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return indicatorDiv;
  }

  function removeTypingIndicator() {
    const indicator = document.getElementById("typing-indicator");
    if (indicator) {
      indicator.remove();
    }
  }

  function appendAssistantMessage(replyText, sources = [], isLeadCaptured = false) {
    removeTypingIndicator();

    const messageDiv = document.createElement("div");
    messageDiv.classList.add("message", "message-assistant");

    const bubble = document.createElement("div");
    bubble.classList.add("message-bubble");

    // Formatted markdown content
    bubble.innerHTML = formatMarkdown(replyText);

    // RAG sources footer if available
    if (sources && sources.length > 0) {
      const sourcesBox = document.createElement("div");
      sourcesBox.classList.add("chat-sources-box");

      const title = document.createElement("div");
      title.classList.add("chat-sources-label");
      title.innerHTML = `<span>🔍 Подтверждённые источники RAG (${sources.length}):</span>`;
      sourcesBox.appendChild(title);

      const list = document.createElement("div");
      list.classList.add("chat-sources-chips");

      sources.forEach((src) => {
        const item = document.createElement("a");
        item.classList.add("chat-source-chip");
        item.textContent = src.title;
        if (src.url) {
          item.href = src.url;
          item.target = "_blank";
          item.rel = "noopener noreferrer";
        } else {
          item.href = "#";
          item.addEventListener("click", (e) => e.preventDefault());
        }
        if (src.score) {
          const scoreBadge = document.createElement("span");
          scoreBadge.classList.add("source-score");
          scoreBadge.textContent = `${Math.round(src.score * 100)}%`;
          item.appendChild(scoreBadge);
        }
        list.appendChild(item);
      });

      sourcesBox.appendChild(list);
      bubble.appendChild(sourcesBox);
    }

    // Lead capture badge if contacts were captured in this turn
    if (isLeadCaptured) {
      const leadBadge = document.createElement("div");
      leadBadge.classList.add("chat-lead-captured-badge");
      leadBadge.innerHTML = "<span>✓ Контакты зафиксированы и переданы Андрису на email</span>";
      bubble.appendChild(leadBadge);
    }

    messageDiv.appendChild(bubble);
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    conversationHistory.push({ role: "assistant", content: replyText });
  }

  async function handleSendMessage(userText) {
    const trimmed = userText.trim();
    if (!trimmed) return;

    appendUserMessage(trimmed);
    chatInput.value = "";
    submitBtn.disabled = true;

    createTypingIndicator();

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
        },
        body: JSON.stringify({
          message: trimmed,
          history: conversationHistory,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      const data = await response.json();
      appendAssistantMessage(data.reply, data.sources, data.contact_captured);

      if (data.contact_captured) {
        showLeadNotification(
          data.email_sent
            ? "Ваши контакты успешно доставлены на email Андриса! Он ответит вам в ближайшее время."
            : "Ваши контакты сохранены в системе. Андрис свяжется с вами в ближайшее время."
        );
      }

      if (chatFeedback) {
        chatFeedback.textContent = "Ответ получен.";
      }
    } catch (error) {
      console.error("Chat API error:", error);
      removeTypingIndicator();
      appendAssistantMessage(
        "Произошла ошибка связи с сервером. Пожалуйста, повторите запрос или напишите Андрису напрямую на **andris.jancevskis@gmail.com**."
      );
      if (chatFeedback) {
        chatFeedback.textContent = "Ошибка при обращении к AI-ассистенту.";
      }
    } finally {
      submitBtn.disabled = false;
      chatInput.focus();
    }
  }

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    handleSendMessage(chatInput.value);
  });

  // Prompt chips clicks
  chipButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const action = btn.getAttribute("data-action");
      if (action === "open-contact") {
        const leadCard = document.getElementById("quick-contact-card");
        if (leadCard) {
          leadCard.scrollIntoView({ behavior: "smooth" });
          const leadNameInput = document.getElementById("lead-name");
          if (leadNameInput) leadNameInput.focus();
        }
        return;
      }

      const question = btn.getAttribute("data-question") || btn.textContent.trim();
      chatInput.value = question;
      chatInput.focus();
      handleSendMessage(question);
    });
  });

  // Quick link button to open lead card
  const btnOpenLead = document.getElementById("btn-open-lead-modal");
  if (btnOpenLead) {
    btnOpenLead.addEventListener("click", () => {
      const leadCard = document.getElementById("quick-contact-card");
      if (leadCard) {
        leadCard.scrollIntoView({ behavior: "smooth" });
        const leadNameInput = document.getElementById("lead-name");
        if (leadNameInput) leadNameInput.focus();
      }
    });
  }
}

/**
 * 6. Direct Lead Form Submission with reCAPTCHA
 */
function initDirectLeadForm() {
  const form = document.getElementById("direct-lead-form");
  if (!form) return;

  const nameInput = document.getElementById("lead-name");
  const emailInput = document.getElementById("lead-email");
  const phoneInput = document.getElementById("lead-phone");
  const demandsInput = document.getElementById("lead-demands");
  const submitBtn = document.getElementById("lead-submit-btn");
  const btnText = submitBtn ? submitBtn.querySelector(".btn-text") : null;
  const btnSpinner = submitBtn ? submitBtn.querySelector(".btn-spinner") : null;
  const btnArrow = submitBtn ? submitBtn.querySelector(".btn-arrow") : null;
  const alertBox = document.getElementById("lead-card-alert");

  function showLeadCardAlert(type, message) {
    if (!alertBox) return;
    alertBox.className = "contact-alert " + (type === "success" ? "contact-alert-success" : "contact-alert-error");
    alertBox.textContent = message;
    alertBox.style.display = "block";
  }

  function hideLeadCardAlert() {
    if (!alertBox) return;
    alertBox.style.display = "none";
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideLeadCardAlert();

    const name = (nameInput?.value || "").trim();
    const email = (emailInput?.value || "").trim();
    const phone = (phoneInput?.value || "").trim();
    const demands = (demandsInput?.value || "").trim();

    if (!name || name.length < 2) {
      showLeadCardAlert("error", "Пожалуйста, укажите ваше имя (не менее 2 символов).");
      if (nameInput) nameInput.focus();
      return;
    }

    if (!email || !email.includes("@")) {
      showLeadCardAlert("error", "Пожалуйста, введите корректный адрес электронной почты.");
      if (emailInput) emailInput.focus();
      return;
    }

    // Google reCAPTCHA check
    let recaptchaToken = null;
    if (typeof grecaptcha !== "undefined" && typeof grecaptcha.getResponse === "function") {
      recaptchaToken = grecaptcha.getResponse();
      if (!recaptchaToken) {
        showLeadCardAlert("error", "Пожалуйста, подтвердите reCAPTCHA («Я не робот»).");
        return;
      }
    }

    if (submitBtn) submitBtn.disabled = true;
    if (btnText) btnText.textContent = "Отправка...";
    if (btnArrow) btnArrow.style.display = "none";
    if (btnSpinner) btnSpinner.style.display = "inline";

    try {
      const response = await fetch("/api/chat/lead", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
        },
        body: JSON.stringify({
          name: name,
          email: email,
          phone: phone || null,
          demands: demands || null,
          recaptcha_token: recaptchaToken,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (response.ok && data.success) {
        showLeadCardAlert("success", data.message || "Контакты успешно отправлены Андрису!");
        const banner = document.getElementById("lead-notification-banner");
        const bannerText = document.getElementById("lead-banner-text");
        if (banner) {
          if (bannerText) bannerText.textContent = data.message;
          banner.hidden = false;
          banner.scrollIntoView({ behavior: "smooth" });
        }
        form.reset();
        if (typeof grecaptcha !== "undefined" && typeof grecaptcha.reset === "function") {
          try { grecaptcha.reset(); } catch (err) {}
        }
        if (btnText) btnText.textContent = "✓ Заявка отправлена";
      } else {
        const detail = data.detail || data.message || "Не удалось отправить заявку. Попробуйте снова.";
        showLeadCardAlert("error", detail);
        if (btnText) btnText.textContent = "Отправить контакты Андрису";
        if (btnArrow) btnArrow.style.display = "inline";
        if (submitBtn) submitBtn.disabled = false;
      }
    } catch (err) {
      console.error("Lead submission error:", err);
      showLeadCardAlert("error", "Сетевая ошибка при отправке. Проверьте соединение и попробуйте снова.");
      if (btnText) btnText.textContent = "Отправить контакты Андрису";
      if (btnArrow) btnArrow.style.display = "inline";
      if (submitBtn) submitBtn.disabled = false;
    } finally {
      if (btnSpinner) btnSpinner.style.display = "none";
    }
  });
}
