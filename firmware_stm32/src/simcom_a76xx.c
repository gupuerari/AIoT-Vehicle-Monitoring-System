#include "app_config.h"
#include "certificates.h"

typedef struct { uint8_t buffer[MODEM_RX_BUFFER_SIZE]; volatile uint16_t head; volatile uint16_t tail; } RingBuffer_t;
static RingBuffer_t modem_rx_buffer;

void Modem_UART_Init(void) {
    modem_rx_buffer.head = 0; modem_rx_buffer.tail = 0;
    HAL_UART_Receive_IT(&huart1, &modem_rx_buffer.buffer[modem_rx_buffer.head], 1);
}
void Modem_RX_Callback(void) {
    modem_rx_buffer.head = (modem_rx_buffer.head + 1) % MODEM_RX_BUFFER_SIZE;
    HAL_UART_Receive_IT(&huart1, &modem_rx_buffer.buffer[modem_rx_buffer.head], 1);
}

bool Send_AT_Command(const char* cmd, const char* expected_response, uint32_t timeout) {
    char local_buf[MODEM_RX_BUFFER_SIZE+1]={0}; uint16_t idx=0;
    modem_rx_buffer.tail = modem_rx_buffer.head;
    if(cmd && strlen(cmd)>0) HAL_UART_Transmit(&huart1, (uint8_t*)cmd, strlen(cmd), HAL_MAX_DELAY);
    uint32_t start = HAL_GetTick();
    while(HAL_GetTick()-start < timeout) {
        if(modem_rx_buffer.tail != modem_rx_buffer.head) {
            local_buf[idx++] = modem_rx_buffer.buffer[modem_rx_buffer.tail];
            modem_rx_buffer.tail = (modem_rx_buffer.tail+1) % MODEM_RX_BUFFER_SIZE;
            if(strstr(local_buf, expected_response)) return true;
            if(idx >= MODEM_RX_BUFFER_SIZE-1) idx=0;
        }
    }
    return false;
}

// --- FUNCOES PRIVADAS DE CERTIFICADO ---
static bool Upload_Certificate(const char* filename, const char* content) {
    char cmd[128]; sprintf(cmd, "AT+CCERTDOWN=\"%s\",%d\r\n", filename, (int)strlen(content));
    if(!Send_AT_Command(cmd, ">", 5000)) return false;
    // Envia em blocos
    for(int i=0; i<strlen(content); i+=128) {
        int chunk = (strlen(content)-i < 128) ? strlen(content)-i : 128;
        HAL_UART_Transmit(&huart1, (uint8_t*)content+i, chunk, HAL_MAX_DELAY); HAL_Delay(50);
    }
    return Send_AT_Command("", "OK", 30000);
}

bool SIMCOM_Certificates_CheckAndUpload(void) {
    // Simplificado: Tenta deletar e subir sempre para garantir
    HAL_UART_Transmit(&huart2, (uint8_t*)"[Cert] Atualizando certificados...\r\n", 36, HAL_MAX_DELAY);
    Send_AT_Command("AT+CCERTDELE=\"ca.pem\"\r\n", "OK", 2000);
    if(!Upload_Certificate("ca.pem", AWS_ROOT_CA_PEM)) return false;
    Send_AT_Command("AT+CCERTDELE=\"device.pem\"\r\n", "OK", 2000);
    if(!Upload_Certificate("device.pem", AWS_DEVICE_CERT_PEM)) return false;
    Send_AT_Command("AT+CCERTDELE=\"private.pem\"\r\n", "OK", 2000);
    if(!Upload_Certificate("private.pem", AWS_PRIVATE_KEY_PEM)) return false;
    return true;
}

bool SIMCOM_Init_Sequence(void) {
    HAL_UART_Transmit(&huart2, (uint8_t*)"[Modem] Init...\r\n", 17, HAL_MAX_DELAY);
    Send_AT_Command("ATE0\r\n", "OK", 1000);
    if(!Send_AT_Command("AT\r\n", "OK", 1000)) return false;
    if(!Send_AT_Command("AT+CPIN?\r\n", "READY", 5000)) return false;
    Send_AT_Command("AT+CGDCONT=1,\"IP\",\"zap.vivo.com.br\"\r\n", "OK", 2000);
    for(int i=0; i<5; i++) { if(Send_AT_Command("AT+CGREG?\r\n", "0,1", 1000)) break; HAL_Delay(1000); if(i==4) return false; }
    return SIMCOM_Certificates_CheckAndUpload();
}

bool SIMCOM_Publish_Event(const char* json_payload) {
    char cmd[256];
    Send_AT_Command("AT+CMQTTSTOP\r\n", "OK", 2000); HAL_Delay(500);
    if(!Send_AT_Command("AT+CMQTTSTART\r\n", "+CMQTTSTART: 0", 10000)) return false;
    sprintf(cmd, "AT+CMQTTACCQ=0,\"STM32_DEV\",1\r\n");
    if(!Send_AT_Command(cmd, "OK", 5000)) return false;
    
    Send_AT_Command("AT+CSSLCFG=\"sslversion\",0,4\r\n", "OK", 5000);
    Send_AT_Command("AT+CSSLCFG=\"authmode\",0,2\r\n", "OK", 5000);
    Send_AT_Command("AT+CSSLCFG=\"cacert\",0,\"ca.pem\"\r\n", "OK", 5000);
    Send_AT_Command("AT+CSSLCFG=\"clientcert\",0,\"device.pem\"\r\n", "OK", 5000);
    Send_AT_Command("AT+CSSLCFG=\"clientkey\",0,\"private.pem\"\r\n", "OK", 5000);
    Send_AT_Command("AT+CMQTTSSLCFG=0,0\r\n", "OK", 2000);

    sprintf(cmd, "AT+CMQTTCONNECT=0,\"tcp://a3s3fmkum72xz8-ats.iot.us-east-2.amazonaws.com:8883\",60,1\r\n");
    if(!Send_AT_Command(cmd, "+CMQTTCONNECT: 0,0", 20000)) return false;

    sprintf(cmd, "AT+CMQTTTOPIC=0,%d\r\n", 35);
    if(Send_AT_Command(cmd, ">", 2000)) Send_AT_Command("veiculos/STM32_VERSAO_FINAL/eventos", "OK", 2000);

    sprintf(cmd, "AT+CMQTTPAYLOAD=0,%d\r\n", (int)strlen(json_payload));
    if(Send_AT_Command(cmd, ">", 2000)) Send_AT_Command(json_payload, "OK", 5000);

    bool res = Send_AT_Command("AT+CMQTTPUB=0,1,60\r\n", "+CMQTTPUB: 0,0", 15000);
    Send_AT_Command("AT+CMQTTDISC=0,60\r\n", "OK", 5000);
    Send_AT_Command("AT+CMQTTREL=0\r\n", "OK", 2000);
    Send_AT_Command("AT+CMQTTSTOP\r\n", "OK", 5000);
    return res;
}