idf_component_register(SRCS "app_main.c" "wire.c" INCLUDE_DIRS "."
                       REQUIRES esp_wifi esp_event esp_netif nvs_flash esp_timer esp_driver_uart)
