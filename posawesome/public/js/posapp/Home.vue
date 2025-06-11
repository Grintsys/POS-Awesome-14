<template>
  <v-app class="container1">
    <v-main>
      <Navbar @changePage="setPage($event)"></Navbar>
      <component v-bind:is="page" class="mx-4 md-4"></component>
    </v-main>
  </v-app>
</template>

<script>
import Navbar from './components/Navbar.vue';
import POS from './components/pos/Pos.vue';
import Payments from './components/payments/Pay.vue';

export default {
  data: function () {
    return {
      page: 'POS',
    };
  },
  components: {
    Navbar,
    POS,
    Payments,
  },
  methods: {
    setPage(page) {
      this.page = page;
    },
    remove_frappe_nav() {
      this.$nextTick(function () {
        $('.page-head').remove();
        $('.navbar.navbar-default.navbar-fixed-top').remove();
      });
    },

    // 👉 INICIO código agregado: advertencia al cerrar o recargar
    handleBeforeUnload(e) {
      if (cur_pos && cur_pos.doc && cur_pos.doc.items && cur_pos.doc.items.length > 0) {
        const confirmationMessage = "⚠️ Hay una venta activa. ¿Seguro que deseas salir?";
        e.preventDefault();
        e.returnValue = confirmationMessage;
        return confirmationMessage;
      }
    },
    // 👉 FIN código agregado
  },
  mounted() {
    this.remove_frappe_nav();

    // 👉 INICIO código agregado: conectar evento beforeunload
    window.addEventListener('beforeunload', this.handleBeforeUnload);
    // 👉 FIN código agregado
  },
  beforeDestroy() {
    // 👉 INICIO código agregado: desconectar evento beforeunload
    window.removeEventListener('beforeunload', this.handleBeforeUnload);
    // 👉 FIN código agregado
  },
  updated() {},
  created: function () {
    setTimeout(() => {
      this.remove_frappe_nav();
    }, 1000);
  },
};
</script>

<style scoped>
.container1 {
  margin-top: 0px;
}
</style>