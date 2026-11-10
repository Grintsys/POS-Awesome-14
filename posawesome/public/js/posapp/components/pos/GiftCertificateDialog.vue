<template>
  <v-row justify="center">
    <!-- Dialog 1: Emitir Certificado de Regalo -->
    <v-dialog
      v-model="emitDialog"
      max-width="620px"
      @click:outside="closeEmitDialog"
    >
      <v-card>
        <v-card-title class="primary white--text">
          <span class="headline">{{ __('Emitir Certificado de Regalo') }}</span>
        </v-card-title>
        <v-card-text class="pt-5 pb-2">
          <v-container class="pa-0">
            <v-row>
              <v-col cols="12" sm="6" class="py-2">
                <v-text-field
                  v-model="comprador"
                  dense
                  outlined
                  hide-details="auto"
                  color="primary"
                  :label="__('Cliente Comprador') + ' *'"
                  background-color="white"
                ></v-text-field>
              </v-col>
              <v-col cols="12" sm="6" class="py-2">
                <v-text-field
                  v-model="beneficiario"
                  dense
                  outlined
                  hide-details="auto"
                  color="primary"
                  :label="__('Para (Portador / Beneficiario)')"
                  background-color="white"
                ></v-text-field>
              </v-col>
              <v-col cols="12" sm="6" class="py-2">
                <v-text-field
                  v-model.number="monto_inicial"
                  dense
                  outlined
                  hide-details="auto"
                  color="primary"
                  :label="__('Monto del Certificado') + ' *'"
                  background-color="white"
                  type="number"
                  step="any"
                ></v-text-field>
              </v-col>
              <v-col cols="12" sm="6" class="py-2">
                <v-select
                  v-model="mode_of_payment"
                  :items="paymentModes"
                  dense
                  outlined
                  hide-details="auto"
                  color="primary"
                  :label="__('Método de Pago Recibido') + ' *'"
                  background-color="white"
                ></v-select>
              </v-col>
              <v-col cols="12" sm="6" class="py-2">
                <v-text-field
                  v-model="referencia_pago"
                  dense
                  outlined
                  hide-details="auto"
                  color="primary"
                  :label="__('No. Referencia / Voucher')"
                  background-color="white"
                ></v-text-field>
              </v-col>
              <v-col cols="12" sm="6" class="py-2">
                <v-text-field
                  v-model="notas"
                  dense
                  outlined
                  hide-details="auto"
                  color="primary"
                  :label="__('Dedicatoria / Nota')"
                  background-color="white"
                ></v-text-field>
              </v-col>
            </v-row>
          </v-container>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="error" dark @click="closeEmitDialog">
            {{ __('Cancelar') }}
          </v-btn>
          <v-btn
            color="success"
            dark
            :loading="submitting"
            @click="submitEmitCertificate"
          >
            {{ __('Validar e Imprimir Voucher') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Dialog 2: Consultar Saldo y Trazabilidad (Sin Lista) -->
    <v-dialog
      v-model="inquiryDialog"
      max-width="760px"
      @click:outside="closeInquiryDialog"
    >
      <v-card>
        <v-card-title class="primary white--text">
          <span class="headline">{{
            __('Consultar Certificado de Regalo (Escáner)')
          }}</span>
        </v-card-title>
        <v-card-text class="pt-4">
          <v-row dense align="center">
            <v-col cols="12" sm="8">
              <v-text-field
                v-model="scanCode"
                dense
                outlined
                color="primary"
                :label="__('Escanear o Digitar 16 dígitos (XXXX-XXXX-XXXX-XXXX)')"
                placeholder="XXXX-XXXX-XXXX-XXXX"
                background-color="white"
                hide-details
                @input="formatScanInput"
                @keyup.enter="lookupCertificate"
              ></v-text-field>
            </v-col>
            <v-col cols="6" sm="2">
              <v-btn
                block
                color="primary"
                dark
                :loading="searching"
                @click="lookupCertificate"
              >
                {{ __('Consultar') }}
              </v-btn>
            </v-col>
            <v-col cols="6" sm="2">
              <v-btn block color="warning" dark @click="clearInquiry">
                {{ __('Limpiar') }}
              </v-btn>
            </v-col>
          </v-row>

          <div v-if="certInfo" class="mt-4">
            <v-card outlined class="pa-3 mb-3 grey lighten-5">
              <v-row dense align="center">
                <v-col cols="12" sm="6">
                  <div class="caption grey--text">
                    {{ __('Certificado Verificado') }}
                  </div>
                  <div class="subtitle-1 font-weight-bold">
                    {{ certInfo.certificado_id }} |
                    {{ certInfo.codigo_enmascarado }}
                  </div>
                  <div class="caption">
                    {{ __('Comprador:') }}
                    {{ certInfo.nombre_comprador || certInfo.comprador }} |
                    {{ __('Portador:') }} {{ certInfo.beneficiario }}
                  </div>
                </v-col>
                <v-col cols="6" sm="3" class="text-right">
                  <div class="caption grey--text">
                    {{ __('Estado / Inicial') }}
                  </div>
                  <div class="subtitle-2 font-weight-bold">
                    {{ certInfo.estado }} ({{ certInfo.monto_inicial }})
                  </div>
                </v-col>
                <v-col cols="6" sm="3" class="text-right">
                  <div class="caption success--text font-weight-bold">
                    {{ __('SALDO DISPONIBLE') }}
                  </div>
                  <div class="title success--text font-weight-bold">
                    {{ certInfo.saldo_disponible }}
                  </div>
                </v-col>
              </v-row>
            </v-card>

            <div class="subtitle-2 font-weight-bold mb-1">
              {{ __('Trazabilidad de Movimientos') }}
            </div>
            <v-simple-table dense class="elevation-1">
              <thead>
                <tr>
                  <th class="text-left">{{ __('Fecha/Hora') }}</th>
                  <th class="text-left">{{ __('Movimiento') }}</th>
                  <th class="text-left">{{ __('Referencia') }}</th>
                  <th class="text-left">{{ __('Cliente') }}</th>
                  <th class="text-right">{{ __('Monto') }}</th>
                  <th class="text-right">{{ __('Saldo') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(h, i) in certInfo.historial" :key="i">
                  <td>{{ h.fecha_hora }}</td>
                  <td>{{ h.tipo_movimiento }}</td>
                  <td>{{ h.documento_referencia }}</td>
                  <td>{{ h.cliente }}</td>
                  <td class="text-right">{{ h.monto }}</td>
                  <td class="text-right font-weight-bold">
                    {{ h.saldo_resultante }}
                  </td>
                </tr>
              </tbody>
            </v-simple-table>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="error" dark @click="closeInquiryDialog">
            {{ __('Cerrar') }}
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
    emitDialog: false,
    inquiryDialog: false,
    submitting: false,
    searching: false,
    pos_opening_shift: '',
    pos_profile: '',
    comprador: '',
    beneficiario: '',
    monto_inicial: 0,
    mode_of_payment: '',
    referencia_pago: '',
    notas: '',
    scanCode: '',
    certInfo: null,
  }),
  computed: {
    paymentModes() {
      if (!this.pos_profile || !this.pos_profile.payments) {
        return ['Efectivo', 'Tarjetas de credito', 'Transferencia bancaria'];
      }
      return this.pos_profile.payments
        .map((p) => p.mode_of_payment)
        .filter((m) => m !== 'Certificado de Regalo');
    },
  },
  methods: {
    closeEmitDialog() {
      this.emitDialog = false;
      this.monto_inicial = 0;
      this.beneficiario = '';
      this.referencia_pago = '';
      this.notas = '';
    },
    closeInquiryDialog() {
      this.inquiryDialog = false;
      this.clearInquiry();
    },
    clearInquiry() {
      this.scanCode = '';
      this.certInfo = null;
    },
    formatScanInput() {
      const raw = (this.scanCode || '').replace(/\D/g, '').slice(0, 16);
      const groups = raw.match(/.{1,4}/g) || [];
      this.scanCode = groups.join('-');
    },
    submitEmitCertificate() {
      if (!this.comprador) {
        evntBus.$emit('show_mesage', {
          text: __('Seleccione o ingrese el Cliente Comprador'),
          color: 'error',
        });
        return;
      }
      if (!this.monto_inicial || this.monto_inicial <= 0) {
        evntBus.$emit('show_mesage', {
          text: __('El Monto del Certificado debe ser mayor a cero'),
          color: 'error',
        });
        return;
      }
      if (!this.mode_of_payment) {
        evntBus.$emit('show_mesage', {
          text: __('Seleccione el Método de Pago Recibido'),
          color: 'error',
        });
        return;
      }

      this.submitting = true;
      frappe.call({
        method:
          'erpnext.accounts.doctype.certificado_de_regalo.certificado_de_regalo.emitir_certificado_desde_pos',
        args: {
          comprador: this.comprador,
          monto_inicial: this.monto_inicial,
          mode_of_payment: this.mode_of_payment,
          company: this.pos_profile.company,
          pos_opening_shift: this.pos_opening_shift,
          pos_profile: this.pos_profile.name,
          beneficiario: this.beneficiario,
          referencia_pago: this.referencia_pago,
          notas: this.notas,
        },
        callback: (r) => {
          this.submitting = false;
          if (!r.exc && r.message && r.message.name) {
            evntBus.$emit('show_mesage', {
              text: __(
                `Certificado ${r.message.name} (${r.message.codigo_enmascarado}) emitido exitosamente.`
              ),
              color: 'success',
            });
            this.printCertificateVoucher(r.message.name);
            this.closeEmitDialog();
          }
        },
        error: () => {
          this.submitting = false;
        },
      });
    },
    printCertificateVoucher(certName) {
      const url =
        frappe.urllib.get_base_url() +
        '/printview?doctype=Certificado%20de%20Regalo&name=' +
        encodeURIComponent(certName) +
        '&trigger_print=1&format=Voucher%20Certificado%20de%20Regalo&no_letterhead=1';
      const printWindow = window.open(url, 'PrintGiftCert');
      if (printWindow) {
        printWindow.addEventListener(
          'load',
          function () {
            printWindow.print();
          },
          true
        );
      }
    },
    lookupCertificate() {
      const cleaned = (this.scanCode || '').replace(/[\s\-]+/g, '');
      if (!cleaned) {
        evntBus.$emit('show_mesage', {
          text: __('Escanee o escriba los 16 dígitos del certificado'),
          color: 'error',
        });
        return;
      }
      this.searching = true;
      frappe.call({
        method:
          'erpnext.accounts.doctype.certificado_de_regalo.certificado_de_regalo.consultar_certificado_por_codigo',
        args: {
          codigo: cleaned,
          company: this.pos_profile ? this.pos_profile.company : null,
        },
        callback: (r) => {
          this.searching = false;
          this.scanCode = '';
          if (!r.exc && r.message) {
            this.certInfo = r.message;
          }
        },
        error: () => {
          this.searching = false;
          this.scanCode = '';
        },
      });
    },
  },
  created() {
    evntBus.$on(
      'open_emit_gift_certificate',
      (pos_opening_shift, pos_profile) => {
        this.pos_opening_shift = pos_opening_shift;
        this.pos_profile = pos_profile;
        this.comprador =
          (pos_profile && pos_profile.customer) || 'Consumidor Final';
        const modes = this.paymentModes;
        this.mode_of_payment = modes.length ? modes[0] : 'Efectivo';
        this.emitDialog = true;
      }
    );
    evntBus.$on('open_inquiry_gift_certificate', (pos_profile) => {
      this.pos_profile = pos_profile;
      this.clearInquiry();
      this.inquiryDialog = true;
    });
  },
};
</script>

