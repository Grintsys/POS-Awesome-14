import Home from './Home.vue';

frappe.provide('frappe.PosApp');

frappe.PosApp.posapp = class {
    constructor({ parent }) {
        this.$parent = $(document);
        this.page = parent.page;
        this.make_body();

        // Aquí agregamos el listener para beforeunload
        window.addEventListener('beforeunload', this.beforeUnloadHandler.bind(this));
        // Opcional: también capturar F5 para confirmación (aunque F5 también dispara beforeunload)
        window.addEventListener('keydown', this.keydownHandler.bind(this));
    }

    make_body () {
        this.$el = this.$parent.find('.main-section');
        this.vue = new Vue({
            vuetify: new Vuetify(
                {
                    rtl: frappe.utils.is_rtl(),
                    theme: {
                        themes: {
                            light: {
                                background: '#FFFFFF',
                                primary: '#0097A7',
                                secondary: '#00BCD4',
                                accent: '#9575CD',
                                success: '#66BB6A',
                                info: '#2196F3',
                                warning: '#FF9800',
                                error: '#E86674',
                                orange: '#E65100',
                                golden: '#A68C59',
                                badge: '#F5528C',
                                customPrimary: '#085294',
                            },
                        },
                    },
                }
            ),
            el: this.$el[0],
            data: {
                // Puedes agregar un flag para saber si hay productos cargados sin guardar
                unsavedProducts: false,
            },
            render: h => h(Home),
        });
    }

    beforeUnloadHandler(event) {
        if (this.vue && this.vue.unsavedProducts) {
            const message = 'Hay productos sin guardar, ¿seguro que quieres salir?';
            event.returnValue = message;
            return message;
        }
    }
    keydownHandler(event) {
        const isF5 = event.key === 'F5';
        const isCtrlR = event.key.toLowerCase() === 'r' && event.ctrlKey;
        const isCmdR = event.key.toLowerCase() === 'r' && event.metaKey;

        if ((isF5 || isCtrlR || isCmdR) && this.vue && this.vue.unsavedProducts) {
            const confirmReload = confirm('⚠️ Hay productos sin guardar. ¿Seguro que quieres recargar la página?');
            if (!confirmReload) {
                event.preventDefault();
            }
        }
    }

    setup_header () {

    }

};

if (frappe.boot && frappe.boot.module_app && frappe.boot.module_app["posawesome"] === "posawesome") {
  window.addEventListener("beforeunload", function (e) {
    console.log("🔁 Evento beforeunload detectado");
    const confirmationMessage = "⚠️ ¿Estás seguro que quieres salir del POS?";
    e.preventDefault();
    e.returnValue = confirmationMessage;
    return confirmationMessage;
  });
}
