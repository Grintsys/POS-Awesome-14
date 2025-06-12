import Home from './Home.vue';

frappe.provide('frappe.PosApp');

frappe.PosApp.posapp = class {
    constructor({ parent }) {
        this.$parent = $(document);
        this.page = parent.page;

        if (frappe.boot?.module_app?.posawesome === "posawesome") {
            this.make_body();

            // Flag global para verificar desde POS.vue
            window.hasUnsavedProducts = false;

            window.addEventListener('beforeunload', this.beforeUnloadHandler.bind(this));
            window.addEventListener('keydown', this.keydownHandler.bind(this));
        }
    }

    make_body () {
        this.$el = this.$parent.find('.main-section');
        this.vue = new Vue({
            vuetify: new Vuetify({
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
            }),
            el: this.$el[0],
            render: h => h(Home),
        });
    }

    beforeUnloadHandler(event) {
        if (window.hasUnsavedProducts) {
            const message = '⚠️ Hay productos sin guardar, ¿seguro que quieres salir del POS?';
            event.preventDefault();
            event.returnValue = message;
            return message;
        }
    }

    keydownHandler(event) {
        const isF5 = event.key === 'F5';
        const isCtrlR = event.key.toLowerCase() === 'r' && event.ctrlKey;
        const isCmdR = event.key.toLowerCase() === 'r' && event.metaKey;

        if ((isF5 || isCtrlR || isCmdR) && window.hasUnsavedProducts) {
            const confirmReload = confirm('⚠️ Hay productos sin guardar. ¿Seguro que quieres recargar la página?');
            if (!confirmReload) {
                event.preventDefault();
                event.stopPropagation();
            }
        }
    }

    setup_header () {}
};
