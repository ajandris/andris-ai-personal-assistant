/**
 * Frontend logic for Andris Jancevskis Portfolio & AI-Assistant
 * Stage 3 MVP implementation
 */

document.addEventListener("DOMContentLoaded", () => {
  initMobileNavigation();
  initSmoothScroll();
  initAIAssistantChat();
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

  // Close menu when clicking nav link
  navMenu.querySelectorAll(".nav-link, .btn-header-ai").forEach((link) => {
    link.addEventListener("click", () => toggleMenu(true));
  });

  // Close menu with Escape key
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && navMenu.classList.contains("is-open")) {
      toggleMenu(true);
      menuToggle.focus();
    }
  });

  // Close when clicking outside
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
 * 2. Smooth scrolling taking prefers-reduced-motion into account
 */
function initSmoothScroll() {
  const isReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", (event) => {
      const targetId = anchor.getAttribute("href");
      if (!targetId || targetId === "#") return;

      const targetElement = document.querySelector(targetId);
      if (targetElement) {
        event.preventDefault();

        targetElement.scrollIntoView({
          behavior: isReducedMotion ? "auto" : "smooth",
          block: "start",
        });

        // Set focus for keyboard accessibility
        if (targetElement.getAttribute("tabindex") === null) {
          targetElement.setAttribute("tabindex", "-1");
        }
        targetElement.focus({ preventScroll: true });

        // Update URL hash without jumping
        history.pushState(null, "", targetId);
      }
    });
  });
}

/**
 * 3. AI Assistant Chat UI
 */
function initAIAssistantChat() {
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatMessages = document.getElementById("chat-messages");
  const chipButtons = document.querySelectorAll(".chip-btn");
  const chatFeedback = document.getElementById("chat-feedback");

  if (!chatForm || !chatInput || !chatMessages) return;

  const PREPARING_NOTICE =
    "Подключение AI-ассистента подготавливается. В следующей версии он сможет " +
    "отвечать на вопросы о профессиональном опыте, навыках, образовании и проектах Андриса Янчевскиса.";

  function appendMessage(text, type = "user") {
    const messageDiv = document.createElement("div");
    messageDiv.classList.add("message", `message-${type}`);

    const bubble = document.createElement("div");
    bubble.classList.add("message-bubble");

    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    bubble.appendChild(paragraph);

    messageDiv.appendChild(bubble);
    chatMessages.appendChild(messageDiv);

    // Scroll to the bottom of the conversation
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function handleUserQuestion(questionText) {
    const trimmed = questionText.trim();
    if (!trimmed) return;

    // 1. Show user message
    appendMessage(trimmed, "user");

    // 2. Show honest notification immediately without fake delay or simulation
    appendMessage(PREPARING_NOTICE, "notice");

    // 3. Accessibility feedback
    if (chatFeedback) {
      chatFeedback.textContent = "Сообщение отправлено. AI-ассистент находится в подготовке.";
    }

    chatInput.value = "";
  }

  // Form submit handler
  chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    handleUserQuestion(chatInput.value);
  });

  // Example prompt chips handler
  chipButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const question = btn.getAttribute("data-question") || btn.textContent.trim();
      chatInput.value = question;
      chatInput.focus();
      handleUserQuestion(question);
    });
  });
}
