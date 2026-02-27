<template>
  <div class="home">
    <img class="brand-logo" src="/branding/workmage-icon.png" alt="Workmage logo" />
    <h1>Workmage</h1>
    <p class="tagline">Discover and run specialized AI agents</p>
    <div class="actions">
      <router-link to="/marketplace" class="btn">Browse Marketplace</router-link>
      <router-link to="/register" class="btn secondary">Create Account</router-link>
    </div>
  </div>
</template>

<style scoped>
.home {
  text-align: center;
  padding: 3rem;
}
h1 {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}
.brand-logo {
  width: 120px;
  margin-bottom: 0.75rem;
}
.tagline {
  color: var(--wm-text-muted);
  margin-bottom: 2rem;
}
.actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
}
.btn {
  padding: 0.75rem 1.5rem;
  background: var(--wm-primary);
  color: var(--wm-white);
  border-radius: 8px;
  text-decoration: none;
}
.btn.secondary {
  background: var(--wm-bg-soft);
  border: 1px solid var(--wm-border);
}
</style>
