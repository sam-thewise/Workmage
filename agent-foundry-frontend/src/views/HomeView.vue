<template>
  <div class="home">
    <h1>Agent Foundry AI</h1>
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
.tagline {
  color: #94a3b8;
  margin-bottom: 2rem;
}
.actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
}
.btn {
  padding: 0.75rem 1.5rem;
  background: #7c3aed;
  color: white;
  border-radius: 8px;
  text-decoration: none;
}
.btn.secondary {
  background: #334155;
}
</style>
