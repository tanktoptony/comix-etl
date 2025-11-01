// cart.js
// Simple persistent cart using localStorage
// Each cart item: { listingId, title, issueNumber, grade, priceRaw, priceDisplay }

const CART_KEY = "comixcatalog_cart_v1";

// ---- helpers ----

function loadCart() {
  try {
    const raw = localStorage.getItem(CART_KEY);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch (e) {
    console.warn("Cart parse error:", e);
    return [];
  }
}

function saveCart(items) {
  localStorage.setItem(CART_KEY, JSON.stringify(items));
}

function addToCart(item) {
  const cart = loadCart();

  // Check if listing already in cart (don't duplicate same exact copy)
  const exists = cart.some((x) => x.listingId === item.listingId);
  if (!exists) {
    cart.push(item);
    saveCart(cart);
  }

  updateMiniCartHUD();
}

function removeFromCart(listingId) {
  let cart = loadCart();
  cart = cart.filter((x) => x.listingId !== listingId);
  saveCart(cart);
  updateMiniCartHUD();
}

function cartSubtotalCents() {
  const cart = loadCart();
  let totalCents = 0;
  for (let i = 0; i < cart.length; i++) {
    totalCents += Number(cart[i].priceCents || 0);
  }
  return totalCents;
}

function cartSubtotalDollars() {
  return cartSubtotalCents() / 100;
}

function formatMoney(n) {
  // 2 decimal fixed, USD style
  return "$" + Number(n).toFixed(2);
}

// ---- header mini cart ----

function updateMiniCartHUD() {
  const cart = loadCart();

  const miniCountEl = document.getElementById("miniCartCount");
  const miniTotalEl = document.getElementById("miniCartTotal");

  if (miniCountEl) miniCountEl.textContent = cart.length.toString();
  if (miniTotalEl) miniTotalEl.textContent = formatMoney(cartSubtotalDollars());
}

// ---- wire "Add to Cart" buttons on listing pages ----
// We'll look for any .js-add-to-cart buttons and attach click handlers

function initAddToCartButtons() {
  const buttons = document.querySelectorAll(".js-add-to-cart");

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const listingId = btn.getAttribute("data-listing-id");
      const title = btn.getAttribute("data-title");
      const issueNumber = btn.getAttribute("data-issue-number");
      const grade = btn.getAttribute("data-grade");
      const priceCents = btn.getAttribute("data-price-cents"); // string form of integer
      const priceDisplay = btn.getAttribute("data-price-display"); // "$1200.00"

      addToCart({
        listingId,
        title,
        issueNumber,
        grade,
        priceCents,
        priceDisplay,
      });


      // visual feedback
      btn.textContent = "Added ✓";
      btn.classList.add("added-state");
    });
  });
}

// ---- cart page hydration ----
// On /marketplace/cart we'll render rows dynamically if container exists

function renderCartPageIfPresent() {
  const container = document.getElementById("cart-line-items");
  const subtotalEl = document.getElementById("cart-subtotal");
  const shippingEl = document.getElementById("cart-shipping");
  const totalEl = document.getElementById("cart-total");

  if (!container) {
    return; // not on cart page
  }

  const cart = loadCart();
  container.innerHTML = "";

  cart.forEach((item) => {
    const row = document.createElement("div");
    row.className = "cart-row listing-card";

    row.innerHTML = `
            <div class="cart-row-left">
                <div class="strong">${item.title} #${item.issueNumber}</div>
                <div class="tiny muted">Grade: ${item.grade}</div>
                <div class="tiny muted">Listing ID: ${item.listingId}</div>
            </div>
            <div class="cart-row-right">
                <div class="price-text">${item.priceDisplay}</div>
                <button class="remove-btn add-btn" data-remove-id="${item.listingId}">
                    Remove
                </button>
            </div>
        `;

    container.appendChild(row);
  });

  // Attach remove handlers
  container.querySelectorAll("[data-remove-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const listingId = btn.getAttribute("data-remove-id");
      removeFromCart(listingId);
      renderCartPageIfPresent(); // re-render after removal
    });
  });

  // Money math:
  const subCents = cartSubtotalCents();
  const subDollars = subCents / 100;

  // Flat demo shipping. (Could get fancier later.)
  const hasItems = cart.length > 0;
  const shippingFlat = hasItems ? 599 : 0; // in cents
  const shippingDollars = shippingFlat / 100;

  const totalDollars = (subCents + shippingFlat) / 100;

  if (subtotalEl) subtotalEl.textContent = formatMoney(subDollars);
  if (shippingEl) shippingEl.textContent = formatMoney(shippingDollars);
  if (totalEl) totalEl.textContent = formatMoney(totalDollars);
}


// ---- init on page load ----

document.addEventListener("DOMContentLoaded", () => {
  updateMiniCartHUD();
  initAddToCartButtons();
  renderCartPageIfPresent();
});
