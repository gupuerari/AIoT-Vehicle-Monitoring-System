#ifndef SIMCOM_A76XX_H
#define SIMCOM_A76XX_H

#include "app_config.h" // Inclui tipos compartilhados como bool e AppStatus

// --- PROTÓTIPOS DAS FUNÇÕES PÚBLICAS ---
 bool Send_AT_Command(const char* cmd, const char* expected_response, uint32_t timeout);

bool SIMCOM_Certificates_CheckAndUpload(void);

bool SIMCOM_Init_Sequence(void);

void Modem_UART_Init(void);

void Modem_RX_Callback(void);

bool SIMCOM_Publish_Event(const char* json_payload);

bool SIMCOM_Send_SMS(const char* phone_number, const char* message);

bool SIMCOM_Get_Location(float* latitude, float* longitude);

#endif // SIMCOM_A76XX_H