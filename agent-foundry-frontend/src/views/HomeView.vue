<template>
  <div class="home text-center pa-6">
    <img class="brand-logo mb-3" src="/branding/workmage-icon.png" alt="Workmage logo" />
    <h1 class="text-h3 mb-2">Workmage</h1>
    <p class="text-body-large text-medium-emphasis mb-8">Discover and run specialized AI agents</p>
    <div class="d-flex gap-3 justify-center flex-wrap">
      <v-btn color="primary" size="large" to="/marketplace">Browse Marketplace</v-btn>
      <v-btn variant="outlined" color="primary" size="large" to="/register">Create Account</v-btn>
    </div>
  </div>
</template>

<style scoped>
.brand-logo {
  width: 120px;
}
</style>
