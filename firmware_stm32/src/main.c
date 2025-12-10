#include "main.h"
#include "app_config.h"
#include "certificates.h"

// --- DEFINIÇÃO DAS VARIÁVEIS GLOBAIS ---
I2C_HandleTypeDef hi2c1;
UART_HandleTypeDef huart1;
UART_HandleTypeDef huart2;

char g_json_payload[JSON_BUFFER_SIZE];

AppConfig g_config = {
    .pre_trigger_samples = DEFAULT_PRE_TRIGGER_SAMPLES,
    .post_trigger_samples = DEFAULT_POST_TRIGGER_SAMPLES,
    .event_threshold_x = DEFAULT_EVENT_THRESHOLD_X,
    .event_threshold_y = DEFAULT_EVENT_THRESHOLD_Y,
    .sensor_read_delay_ms = DEFAULT_SENSOR_DELAY_MS
};

void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_I2C1_Init(void);
static void MX_USART1_UART_Init(void);
static void MX_USART2_UART_Init(void);

int main(void)
{
  HAL_Init();
  SystemClock_Config();
  MX_GPIO_Init();
  MX_I2C1_Init();
  MX_USART1_UART_Init();
  MX_USART2_UART_Init();

  Modem_UART_Init();
  
  HAL_UART_Transmit(&huart2, (uint8_t*)"\r\n=== SISTEMA TCC v1.0 ===\r\n", 39, HAL_MAX_DELAY);

  Load_Config_From_Flash();

  if (MPU6050_Init() != STATUS_OK) {
      HAL_UART_Transmit(&huart2, (uint8_t*)"ERRO SENSOR!\r\n", 14, HAL_MAX_DELAY);
      Error_Handler();
  }
  MPU6050_Calibrate();

  while (1) 
  {
    int mode = User_Mode();
    if (mode > 0) Blink_Status_LED(mode);

    switch (mode) {
        case 1: // Monitoramento
            if (!SIMCOM_Init_Sequence()) {
                HAL_UART_Transmit(&huart2, (uint8_t*)"Modem Falhou.\r\n", 15, HAL_MAX_DELAY);
                continue;
            }
            HAL_UART_Transmit(&huart2, (uint8_t*)"\r\n[SISTEMA] Monitoramento Iniciado.\r\n", 37, HAL_MAX_DELAY);
            while(1) {
                Normal_Mode();
                HAL_Delay(g_config.sensor_read_delay_ms);
                HAL_GPIO_TogglePin(STATUS_LED_PORT, STATUS_LED_PIN); // Heartbeat visual
            }
            break;
        case 2: // Streaming
            while(1) {
                Sensor_Read_Mode();
                uint8_t ch; if (HAL_UART_Receive(&huart2, &ch, 1, 1) == HAL_OK) break;
            }
            break;
        case 3: Configuration_Mode(); break;
        case 4: AT_Command_PassThrough_Mode(); break;
        case 5: GPS_Test_Mode(); break;
    }
  }
}

// --- FUNÇÕES HAL ---
void SystemClock_Config(void) {
  RCC_OscInitTypeDef RCC_OscInitStruct = {0}; RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE; RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1; RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON; RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9; HAL_RCC_OscConfig(&RCC_OscInitStruct);
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK|RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK; RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2; RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
  HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2);
}
static void MX_I2C1_Init(void) { hi2c1.Instance = I2C1; hi2c1.Init.ClockSpeed = 400000; hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2; hi2c1.Init.OwnAddress1 = 0; hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT; hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE; hi2c1.Init.OwnAddress2 = 0; hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE; hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE; HAL_I2C_Init(&hi2c1); }
static void MX_USART1_UART_Init(void) { huart1.Instance = USART1; huart1.Init.BaudRate = 115200; huart1.Init.WordLength = UART_WORDLENGTH_8B; huart1.Init.StopBits = UART_STOPBITS_1; huart1.Init.Parity = UART_PARITY_NONE; huart1.Init.Mode = UART_MODE_TX_RX; huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE; huart1.Init.OverSampling = UART_OVERSAMPLING_16; HAL_UART_Init(&huart1); }
static void MX_USART2_UART_Init(void) { huart2.Instance = USART2; huart2.Init.BaudRate = 115200; huart2.Init.WordLength = UART_WORDLENGTH_8B; huart2.Init.StopBits = UART_STOPBITS_1; huart2.Init.Parity = UART_PARITY_NONE; huart2.Init.Mode = UART_MODE_TX_RX; huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE; huart2.Init.OverSampling = UART_OVERSAMPLING_16; HAL_UART_Init(&huart2); }
static void MX_GPIO_Init(void) { GPIO_InitTypeDef GPIO_InitStruct = {0}; __HAL_RCC_GPIOC_CLK_ENABLE(); __HAL_RCC_GPIOD_CLK_ENABLE(); __HAL_RCC_GPIOA_CLK_ENABLE(); __HAL_RCC_GPIOB_CLK_ENABLE(); HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET); HAL_GPIO_WritePin(STATUS_LED_PORT, STATUS_LED_PIN, GPIO_PIN_RESET); GPIO_InitStruct.Pin = GPIO_PIN_13; GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP; GPIO_InitStruct.Pull = GPIO_NOPULL; GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW; HAL_GPIO_Init(GPIOC, &GPIO_InitStruct); GPIO_InitStruct.Pin = STATUS_LED_PIN; HAL_GPIO_Init(STATUS_LED_PORT, &GPIO_InitStruct); }
void Blink_Status_LED(int count) { for(int i=0; i<count; i++) { HAL_GPIO_WritePin(STATUS_LED_PORT, STATUS_LED_PIN, GPIO_PIN_SET); HAL_Delay(100); HAL_GPIO_WritePin(STATUS_LED_PORT, STATUS_LED_PIN, GPIO_PIN_RESET); HAL_Delay(150); } }
void Error_Handler(void) { __disable_irq(); while (1) { HAL_GPIO_TogglePin(GPIOC, GPIO_PIN_13); HAL_Delay(100); } }
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) { if (huart->Instance == USART1) Modem_RX_Callback(); }