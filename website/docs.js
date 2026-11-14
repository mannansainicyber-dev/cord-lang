/**
 * Cord Documentation Hub Scripts
 * Search, active TOC highlighting, code copy.
 */

document.addEventListener('DOMContentLoaded', () => {
  initDocsSearch();
  initTocHighlight();
  initDocsCodeCopy();
  initDocsMobileNav();
});

/* Search Filter */
function initDocsSearch() {
  const searchInput = document.getElementById('docsSearchInput');
  const sidebarLinks = document.querySelectorAll('.sidebar-link');
  const sections = document.querySelectorAll('.docs-section');

  if (!searchInput) return;

  // Keyboard shortcut Ctrl+K / Cmd+K
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      searchInput.focus();
    }
  });

  searchInput.addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase().trim();

    sidebarLinks.forEach(link => {
      const text = link.textContent.toLowerCase();
      const parentCat = link.closest('.sidebar-category');
      if (!query || text.includes(query)) {
        link.style.display = 'block';
      } else {
        link.style.display = 'none';
      }
    });

    // Check category visibility
    document.querySelectorAll('.sidebar-category').forEach(cat => {
      const visibleLinks = cat.querySelectorAll('.sidebar-link[style="display: block;"], .sidebar-link:not([style*="display: none"])');
      cat.style.display = visibleLinks.length > 0 ? 'block' : 'none';
    });
  });
}

/* Active Heading & Table of Contents Tracker */
function initTocHighlight() {
  const sections = document.querySelectorAll('.docs-section');
  const navLinks = document.querySelectorAll('.sidebar-link');
  const tocLinks = document.querySelectorAll('.toc-link');

  const observerOptions = {
    root: null,
    rootMargin: '-80px 0px -70% 0px',
    threshold: 0
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.getAttribute('id');
        
        // Update sidebar active link
        navLinks.forEach(link => {
          if (link.getAttribute('href') === `#${id}`) {
            link.classList.add('active');
          } else {
            link.classList.remove('active');
          }
        });

        // Update TOC active link
        tocLinks.forEach(link => {
          if (link.getAttribute('href') === `#${id}`) {
            link.classList.add('active');
          } else {
            link.classList.remove('active');
          }
        });
      }
    });
  }, observerOptions);

  sections.forEach(section => observer.observe(section));
}

/* Code Block Copy */
function initDocsCodeCopy() {
  const copyButtons = document.querySelectorAll('.code-copy-btn');

  copyButtons.forEach(btn => {
    btn.addEventListener('click', async () => {
      const codeWrapper = btn.closest('.code-block-wrapper');
      if (!codeWrapper) return;
      const codeEl = codeWrapper.querySelector('code');
      if (!codeEl) return;

      const codeText = codeEl.textContent.trim();
      try {
        await navigator.clipboard.writeText(codeText);
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        btn.style.color = '#34d399';
        setTimeout(() => {
          btn.textContent = originalText;
          btn.style.color = '';
        }, 2000);
      } catch (err) {
        console.error('Copy failed: ', err);
      }
    });
  });
}

/* Mobile Sidebar Drawer */
function initDocsMobileNav() {
  const toggleBtn = document.getElementById('docsMobileToggle');
  const sidebar = document.querySelector('.docs-sidebar');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });

    // Close when clicking a link on mobile
    const links = sidebar.querySelectorAll('.sidebar-link');
    links.forEach(l => {
      l.addEventListener('click', () => {
        sidebar.classList.remove('open');
      });
    });
  }
}
