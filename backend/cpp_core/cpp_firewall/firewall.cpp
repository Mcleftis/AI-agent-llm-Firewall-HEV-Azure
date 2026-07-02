#include <cstdint>
#include <cstring>
#include <string>
#include <unordered_set>
#include <algorithm>
#include <atomic>

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __attribute__((visibility("default")))
#endif

std::atomic<uint64_t> blocked_requests{0};

const std::unordered_set<std::string> malicious_signatures = {
    "max_throttle", "drop", "fuzz", "override"
};

extern "C" {
    DLL_EXPORT int inspect_can_packet(uint32_t packet_id, const uint8_t* payload, size_t payload_length) {
        if (!payload || payload_length < 8) {
            blocked_requests++;
            return 0;
        }

        float sensor_value;
        uint32_t message_counter;
        std::memcpy(&sensor_value, payload, sizeof(float));
        std::memcpy(&message_counter, payload + sizeof(float), sizeof(uint32_t));

        if (packet_id == 0x666 || packet_id > 0x7FF) {
            blocked_requests++;
            return 0;
        }

        if (sensor_value < -1000.0f || sensor_value > 10000.0f) {
            blocked_requests++;
            return 0;
        }

        return 1;
    }

    DLL_EXPORT int validate_api_command(const char* command) {
        if (!command) {
            blocked_requests++;
            return 0;
        }

        std::string cmd(command);
        std::transform(cmd.begin(), cmd.end(), cmd.begin(), [](unsigned char c){ return std::tolower(c); });

        if (malicious_signatures.find(cmd) != malicious_signatures.end()) {
            blocked_requests++;
            return 0;
        }
        
        return 1;
    }

    DLL_EXPORT int apply_safety_guardrails(float* req_throttle, float* req_brake, float current_speed, float battery_soc) {
        if (!req_throttle || !req_brake) return 0;

        if (*req_brake > 0.05f && *req_throttle > 0.05f) {
            *req_throttle = 0.0f;
            return 1;
        }

        if (current_speed >= 180.0f && *req_throttle > 0.0f) {
            *req_throttle = 0.0f;
            return 1;
        }

        if (battery_soc < 5.0f && *req_throttle > 0.2f) {
            *req_throttle = 0.2f;
            return 1;
        }

        if (*req_throttle < 0.0f) *req_throttle = 0.0f;
        if (*req_throttle > 1.0f) *req_throttle = 1.0f;

        return 0;
    }
}