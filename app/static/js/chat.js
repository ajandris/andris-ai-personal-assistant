/**
 * Frontend logic for Andris Jancevskis Portfolio & AI-Assistant
 * Stage 3 MVP implementation
 */

document.addEventListener("DOMContentLoaded", () => {
  initMobileNavigation();
  initSmoothScroll();
  initActiveNavHighlight();
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

      // If we're on another page and clicking /#about, let standard navigation happen
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
 * 3. Active menu item in header (highlight current page & dynamic scrollspy on sections)
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

  // A. Dedicated Subpages
  if (!isHomePage) {
    if (currentPath === "/experience") {
      const link = navLinks.find((l) => l.getAttribute("href") === "/experience");
      setActiveLink(link, true);
    } else if (currentPath === "/skills") {
      const link = navLinks.find((l) => l.getAttribute("href") === "/skills");
      setActiveLink(link, true);
    } else if (currentPath === "/education") {
      const link = navLinks.find((l) => l.getAttribute("href") === "/education");
      setActiveLink(link, true);
    } else if (currentPath === "/portfolio") {
      const link = navLinks.find((l) => l.getAttribute("href") === "/portfolio");
      setActiveLink(link, true);
    } else if (currentPath === "/contact" || currentPath === "/contacts") {
      const link = navLinks.find((l) => l.getAttribute("href") === "/contact" || l.getAttribute("href") === "/contacts");
      setActiveLink(link, true);
    } else if (currentPath === "/ai-assistant") {
      setActiveLink(aiButton, true);
    }
    return;
  }

  // B. Homepage ScrollSpy for sections
  const sectionIds = ["about", "services", "contact"];
  const sections = sectionIds
    .map((id) => document.getElementById(id))
    .filter((el) => el !== null);

  const sectionMap = new Map();
  sectionIds.forEach((id) => {
    const link = navLinks.find(
      (l) =>
        l.getAttribute("data-nav-section") === id ||
        l.getAttribute("href") === `/#${id}` ||
        l.getAttribute("href") === `#${id}`
    );
    if (link) {
      sectionMap.set(id, link);
    }
  });

  let lockScrollSpy = false;
  let lockTimeout = null;

  function updateActiveSection() {
    if (lockScrollSpy) return;

    // Check if scrolled near the bottom of page -> activate contact
    const scrollBottom = window.innerHeight + window.scrollY;
    const documentHeight = document.documentElement.scrollHeight;
    if (scrollBottom >= documentHeight - 60) {
      if (sectionMap.has("contact")) {
        setActiveLink(sectionMap.get("contact"), false);
        return;
      }
    }

    const header = document.querySelector(".site-header");
    const headerOffset = header ? header.offsetHeight + 60 : 120;
    const scrollPosition = window.scrollY + headerOffset;

    let activeSectionId = null;

    for (let i = 0; i < sections.length; i++) {
      const section = sections[i];
      const top = section.offsetTop;
      const height = section.offsetHeight;

      if (scrollPosition >= top && scrollPosition < top + height) {
        activeSectionId = section.id;
        break;
      }
    }

    if (activeSectionId && sectionMap.has(activeSectionId)) {
      setActiveLink(sectionMap.get(activeSectionId), false);
    } else if (window.scrollY < 200) {
      // At the top of hero section, no anchor section is active
      clearActiveStates();
    }
  }

  // Initial check on load: URL hash or scroll position
  if (window.location.hash) {
    const hashId = window.location.hash.replace("#", "");
    if (sectionMap.has(hashId)) {
      setActiveLink(sectionMap.get(hashId), false);
    } else {
      updateActiveSection();
    }
  } else {
    updateActiveSection();
  }

  // Scroll listener
  let ticking = false;
  window.addEventListener(
    "scroll",
    () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          updateActiveSection();
          ticking = false;
        });
        ticking = true;
      }
    },
    { passive: true }
  );

  // Click on nav links for immediate visual feedback
  navLinks.forEach((link) => {
    const href = link.getAttribute("href");
    if (!href || !href.includes("#")) return;

    const hash = href.slice(href.indexOf("#") + 1);
    link.addEventListener("click", () => {
      if (sectionMap.has(hash)) {
        setActiveLink(link, false);
        lockScrollSpy = true;
        clearTimeout(lockTimeout);
        lockTimeout = setTimeout(() => {
          lockScrollSpy = false;
        }, 900);
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
