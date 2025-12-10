#include "app_config.h"
#include "mpu6050.h"
#include "simcom_a76xx.h"
#include "flash_storage.h"

// Variáveis Estáticas
static MonitorState current_state = STATE_MONITORING;
static SensorSample pre_trigger_buffer[MAX_SAMPLES];
static SensorSample post_trigger_buffer[MAX_SAMPLES];
static uint32_t pre_trigger_index = 0;
static uint32_t post_trigger_count = 0;
static uint32_t trigger_timestamp = 0;

// Variável para controle do Keep Alive (NOVO)
static uint32_t last_activity_timestamp = 0;

float Ax, Ay, Az, Gx, Gy, Gz;

extern int16_t Accel_X_RAW, Accel_Y_RAW, Accel_Z_RAW;
extern int16_t Accel_X_OFFSET, Accel_Y_OFFSET, Accel_Z_OFFSET;
extern int16_t Gyro_X_RAW, Gyro_Y_RAW, Gyro_Z_RAW;
extern int16_t Gyro_X_OFFSET, Gyro_Y_OFFSET, Gyro_Z_OFFSET;

void ReadLine(char* buffer, uint16_t size) {
    uint16_t i = 0; char rx; memset(buffer, 0, size);
    while (i < size-1) {
        if(HAL_UART_Receive(&huart2, (uint8_t*)&rx, 1, HAL_MAX_DELAY)==HAL_OK) {
            if(rx=='\r'){ HAL_UART_Transmit(&huart2, (uint8_t*)"\r\n", 2, HAL_MAX_DELAY); break; }
            else if(rx=='\b' || rx==127) { if(i>0){i--; HAL_UART_Transmit(&huart2, (uint8_t*)"\b \b", 3, HAL_MAX_DELAY);} }
            else { buffer[i++]=rx; HAL_UART_Transmit(&huart2, (uint8_t*)&rx, 1, HAL_MAX_DELAY); }
        }
    }
}

static char* f_to_a(float f, char* buf, int precision) {
    sprintf(buf, "%.*f", precision, f); return buf;
}

void Build_JSON(void) {
    char tmp[32]; memset(g_json_payload, 0, JSON_BUFFER_SIZE);
    
    sprintf(g_json_payload, "{\"dev\":\"%s\",\"ts\":%lu,\"thr\":[%.2f,%.2f],", 
            DEVICE_ID, trigger_timestamp, g_config.event_threshold_x, g_config.event_threshold_y);

    const char* keys[] = {"\"t\":[", "],\"ax\":[", "],\"ay\":[", "],\"az\":[", "],\"gx\":[", "],\"gy\":[", "],\"gz\":["};
    uint32_t start = pre_trigger_index;

    for (int k = 0; k < 7; k++) {
        strcat(g_json_payload, keys[k]);
        // Pré-Evento
        for (uint32_t i = 0; i < g_config.pre_trigger_samples; i++) {
            SensorSample *s = &pre_trigger_buffer[(start + i) % g_config.pre_trigger_samples];
            if(k==0) sprintf(tmp, "%lu", s->timestamp_ms);
            else { 
                float v=0; 
                if(k==1)v=s->ax; else if(k==2)v=s->ay; else if(k==3)v=s->az; 
                else if(k==4)v=s->gx; else if(k==5)v=s->gy; else if(k==6)v=s->gz; 
                f_to_a(v, tmp, 2); 
            }
            strcat(g_json_payload, tmp); strcat(g_json_payload, ",");
        }
        // Pós-Evento
        for (uint32_t i = 0; i < g_config.post_trigger_samples; i++) {
            SensorSample *s = &post_trigger_buffer[i];
            if(k==0) sprintf(tmp, "%lu", s->timestamp_ms);
            else { 
                float v=0; 
                if(k==1)v=s->ax; else if(k==2)v=s->ay; else if(k==3)v=s->az; 
                else if(k==4)v=s->gx; else if(k==5)v=s->gy; else if(k==6)v=s->gz; 
                f_to_a(v, tmp, 2); 
            }
            strcat(g_json_payload, tmp); 
            if(i < g_config.post_trigger_samples - 1) strcat(g_json_payload, ",");
        }
    }
    strcat(g_json_payload, "]}");
}

void Normal_Mode(void) {
    // 1. Leitura
    MPU6050_Read_All();
    // Conversão
    Ax = ((Accel_X_RAW - Accel_X_OFFSET) / 16384.0f) * 9.81f;
    Ay = ((Accel_Y_RAW - Accel_Y_OFFSET) / 16384.0f) * 9.81f;
    Az = ((Accel_Z_RAW - Accel_Z_OFFSET) / 16384.0f) * 9.81f;
    Gx = (Gyro_X_RAW - Gyro_X_OFFSET) / 131.0f;
    Gy = (Gyro_Y_RAW - Gyro_Y_OFFSET) / 131.0f;
    Gz = (Gyro_Z_RAW - Gyro_Z_OFFSET) / 131.0f;

    // Inicializa o timer na primeira rodada
    if (last_activity_timestamp == 0) last_activity_timestamp = HAL_GetTick();

    switch (current_state) {
        case STATE_MONITORING:
            pre_trigger_buffer[pre_trigger_index] = (SensorSample){HAL_GetTick(), Ax, Ay, Az, Gx, Gy, Gz};
            pre_trigger_index = (pre_trigger_index + 1) % g_config.pre_trigger_samples;

            // --- VERIFICAÇÃO DE EVENTOS ---
            
            bool threshold_event = (fabs(Ax) > g_config.event_threshold_x || fabs(Ay) > g_config.event_threshold_y);
            bool keep_alive_event = ((HAL_GetTick() - last_activity_timestamp) > KEEP_ALIVE_INTERVAL_MS);

            if (threshold_event || keep_alive_event) {
                if (threshold_event) {
                    HAL_UART_Transmit(&huart2, (uint8_t*)ANSI_COLOR_YELLOW "\r\n[EVENTO] Impacto! Capturando...\r\n" ANSI_COLOR_RESET, 62, HAL_MAX_DELAY);
                } else {
                    HAL_UART_Transmit(&huart2, (uint8_t*)ANSI_COLOR_CYAN "\r\n[EVENTO] Keep Alive (2min). Capturando...\r\n" ANSI_COLOR_RESET, 69, HAL_MAX_DELAY);
                }

                trigger_timestamp = HAL_GetTick();
                post_trigger_count = 0;
                current_state = STATE_POST_TRIGGER;
                
                // Reseta o timer de Keep Alive sempre que QUALQUER evento ocorre
                last_activity_timestamp = HAL_GetTick();
            }
            break;

        case STATE_POST_TRIGGER:
            post_trigger_buffer[post_trigger_count++] = (SensorSample){HAL_GetTick(), Ax, Ay, Az, Gx, Gy, Gz};
            if (post_trigger_count >= g_config.post_trigger_samples) {
                current_state = STATE_PROCESSING;
            }
            break;

        case STATE_PROCESSING:
            HAL_UART_Transmit(&huart2, (uint8_t*)"[CORE] Gerando JSON e Enviando...\r\n", 35, HAL_MAX_DELAY);
            Build_JSON();
            SIMCOM_Publish_Event(g_json_payload);
            
            current_state = STATE_MONITORING;
            // Atualiza o timestamp novamente ao terminar para não disparar outro KA imediatamente
            last_activity_timestamp = HAL_GetTick();
            HAL_UART_Transmit(&huart2, (uint8_t*)ANSI_COLOR_GREEN "[CORE] Monitoramento Ativo.\r\n" ANSI_COLOR_RESET, 46, HAL_MAX_DELAY);
            break;
    }
}

void Sensor_Read_Mode(void) {
    char buffer[100]; MPU6050_Read_All();
    float d_ax = ((Accel_X_RAW - Accel_X_OFFSET) / 16384.0f) * 9.81f;
    float d_ay = ((Accel_Y_RAW - Accel_Y_OFFSET) / 16384.0f) * 9.81f;
    float d_az = ((Accel_Z_RAW - Accel_Z_OFFSET) / 16384.0f) * 9.81f;
    sprintf(buffer, "ACC: X=%+05.2f Y=%+05.2f Z=%+05.2f\r", d_ax, d_ay, d_az);
    HAL_UART_Transmit(&huart2, (uint8_t*)buffer, strlen(buffer), HAL_MAX_DELAY);
    Blink_Status_LED(1); HAL_Delay(100);
}
              
int User_Mode(void) {
    uint8_t rx;
    const char *menu_str = 
        "\r\n\033[2J\033[H" 
        ANSI_COLOR_CYAN
        "=========================================\r\n"
        "      MONITORAMENTO VEICULAR (TCC)       \r\n"
        "=========================================\r\n"
        ANSI_COLOR_RESET
        "  [1] Iniciar Monitoramento\r\n"
        "  [2] Stream de Sensores (Raw)\r\n"
        "  [3] Configuracao de Parametros\r\n"
        "  [4] Terminal AT (Pass-Through)\r\n"
        "  [5] Teste de GPS\r\n"
        "-----------------------------------------\r\n"
        ANSI_COLOR_YELLOW "  >> Digite a opcao: " ANSI_COLOR_RESET;

    HAL_UART_Transmit(&huart2, (uint8_t*)menu_str, strlen(menu_str), HAL_MAX_DELAY);

    if (HAL_UART_Receive(&huart2, &rx, 1, 10000) == HAL_OK) {
        // Ecoar o caractere digitado para o usuário ver
        HAL_UART_Transmit(&huart2, &rx, 1, HAL_MAX_DELAY);
        if (rx >= '1' && rx <= '5') return rx - '0';
    }
    return 1; 
}

void Configuration_Mode(void) {
    char buf[300]; char opt;
    while(1) {
        sprintf(buf, 
            "\r\n\033[2J\033[H"
            ANSI_COLOR_MAGENTA
            "--- CONFIGURACAO DE PARAMETROS ---\r\n"
            ANSI_COLOR_RESET
            "\r\n"
            "  [1] Amostras Pre-Event  : " ANSI_COLOR_GREEN "%-4d" ANSI_COLOR_RESET " (buffer circular)\r\n"
            "  [2] Amostras Pos-Event  : " ANSI_COLOR_GREEN "%-4d" ANSI_COLOR_RESET " (buffer circular)\r\n"
            "  [3] Threshold X : " ANSI_COLOR_GREEN "%-5.1f" ANSI_COLOR_RESET " m/s^2\r\n"
            "  [4] Threshold Y  : " ANSI_COLOR_GREEN "%-5.1f" ANSI_COLOR_RESET " m/s^2\r\n"
            "\r\n"
            "----------------------------------\r\n"
            "  [d] Restaurar Padroes\r\n"
            "  [x] Salvar e Sair\r\n"
            "\r\n"
            ANSI_COLOR_YELLOW "  >> Editar opcao: " ANSI_COLOR_RESET,
            g_config.pre_trigger_samples, 
            g_config.post_trigger_samples, 
            g_config.event_threshold_x,
            g_config.event_threshold_y 
        );

        HAL_UART_Transmit(&huart2, (uint8_t*)buf, strlen(buf), HAL_MAX_DELAY);
        if(HAL_UART_Receive(&huart2, (uint8_t*)&opt, 1, HAL_MAX_DELAY)==HAL_OK) {
             HAL_UART_Transmit(&huart2, (uint8_t*)&opt, 1, HAL_MAX_DELAY);
             if(opt=='x') { Save_Config_To_Flash(); return; }
             if(opt=='d') Restore_Default_Config();
             if(opt=='1') { HAL_UART_Transmit(&huart2, (uint8_t*)" Novo: ", 7, HAL_MAX_DELAY); ReadLine(buf,10); g_config.pre_trigger_samples=atoi(buf); }
             if(opt=='2') { HAL_UART_Transmit(&huart2, (uint8_t*)" Novo: ", 7, HAL_MAX_DELAY); ReadLine(buf,10); g_config.post_trigger_samples=atoi(buf);}
             if(opt=='3') { HAL_UART_Transmit(&huart2, (uint8_t*)" Novo: ", 7, HAL_MAX_DELAY); ReadLine(buf,10); g_config.event_threshold_x=atof(buf); }
             if(opt=='4') { HAL_UART_Transmit(&huart2, (uint8_t*)" Novo: ", 7, HAL_MAX_DELAY); ReadLine(buf,10); g_config.event_threshold_y=atof(buf); }
        }
    }
}

void AT_Command_PassThrough_Mode(void) {
    uint8_t ch; HAL_UART_Transmit(&huart2, (uint8_t*)"\r\n[AT] 'x' para sair.\r\n", 23, HAL_MAX_DELAY);
    while(1) {
        if(HAL_UART_Receive(&huart1, &ch, 1, 0)==HAL_OK) HAL_UART_Transmit(&huart2, &ch, 1, 10);
        if(HAL_UART_Receive(&huart2, &ch, 1, 0)==HAL_OK) { if(ch=='x') break; HAL_UART_Transmit(&huart1, &ch, 1, 10); }
    }
    extern void Modem_UART_Init(void); Modem_UART_Init();
}

void GPS_Test_Mode(void) {
    Send_AT_Command("AT+CGNSSPWR=1\r\n", "OK", 2000); HAL_Delay(1000); Send_AT_Command("AT+CGNSSINFO\r\n", "+CGNSSINFO", 2000);
}