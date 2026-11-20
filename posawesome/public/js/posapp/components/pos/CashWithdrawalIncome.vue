<template>
  <v-row justify="center">
    <v-dialog
      v-model="cashDialog"
      max-width="600px"
      @click:outside="clear_data"
    >
      <v-card>
        <v-card-title>
          <span class="headline primary--text">{{
            __('Crear Ingreso/Retiro de efectivo')
          }}</span>
        </v-card-title>
        <v-card-text class="pa-0">
          <v-container>
            <v-row>
              <v-col cols="6">
                <v-select
                  dense
                  label="Tipo"
                  :items="types"
                  v-model="type"
                ></v-select>
              </v-col>
              <v-col cols="6">
                <v-text-field
                  v-model.number="amount"
                  dense
                  color="primary"
                  :label="frappe._('Monto') + ' *'"
                  background-color="white"
                  hide-details
                  type="number"
                  step="any"
                ></v-text-field>
              </v-col>
              <v-col cols="12">
                <v-text-field
                  dense
                  color="primary"
                  :label="frappe._('Nota')"
                  background-color="white"
                  hide-details
                  v-model="note"
                ></v-text-field>
              </v-col>
            </v-row>
          </v-container>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="error" dark @click="close_dialog">
            {{ __('Close') }}
          </v-btn>
          <v-btn color="success" dark @click="submit_dialog">
            {{ __('Submit') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-row>
</template>

<script>
import { evntBus } from '../../bus';

export default {
  data: () => ({
    cashDialog: false,
    amount: 0,
    note: '',
    types: ['Retiro', 'Ingreso'],
    type: '',
    pos_opening_shift: '',
    pos_profile: '',
  }),
  methods: {
    close_dialog() {
      this.cashDialog = false;
      this.clear_data();
    },
    clear_data() {
      this.amount = 0;
      this.note = '';
      this.type = '';
      this.pos_opening_shift = '';
    },
    submit_dialog() {
      if (!this.type) {
        evntBus.$emit('show_mesage', {
          text: __('Tipo de transacción es requerido'),
          color: 'error',
        });
        return;
      }
      
      if (this.amount === 0) {
        evntBus.$emit('show_mesage', {
          text: __('Monto es requerido'),
          color: 'error',
        });
        return;
      }

      if (!this.note) {
        evntBus.$emit('show_mesage', {
          text: __('Nota es requerido'),
          color: 'error',
        });
        return;
      }      

      const args = {
        amount: this.amount,
        pos_opening_shift: this.pos_opening_shift,
        note: this.note,
        type_transaction: this.type,
      };

      frappe.call({
        method: 'posawesome.posawesome.api.posapp.create_withdrawal_income',
        args,
        callback: (r) => {
          if (!r.exc && r.message.name) {
            let text = __('Creado exitosamente.');
            
            evntBus.$emit('show_mesage', { text: text, color: 'success' });
            this.load_print_page(r.message.name);
            this.close_dialog();
          } else {
            frappe.utils.play_sound('error');
            evntBus.$emit('show_mesage', {
              text: __('Fallo la transacción.'),
              color: 'error',
            });
          }
        },
      });
    },
    load_print_page(nameMovement) {
      const print_format =
        this.pos_profile.print_format_for_online ||
        this.pos_profile.cash_movements_format;
      const letter_head = this.pos_profile.letter_head || 0;
      const url =
        frappe.urllib.get_base_url() +
        "/printview?doctype=Retiro%20de%20efectivo&name=" +
        nameMovement +
        "&trigger_print=1" +
        "&format=" +
        print_format +
        "&no_letterhead=" +
        letter_head;
      const printWindow = window.open(url, "Print");
      printWindow.addEventListener(
        "load",
        function () {
          printWindow.print();
          // printWindow.close();
          // NOTE : uncomoent this to auto closing printing window
        },
        true
      );
    },
  },
  created() {
    evntBus.$on('open_cash_withdrawal_income', (pos_opening_shift, pos_profile) => {
      this.cashDialog = true;
      this.pos_opening_shift = pos_opening_shift;
      this.pos_profile = pos_profile;
    });
  },
};
</script>