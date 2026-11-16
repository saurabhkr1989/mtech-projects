/**
 * @file MinutiaeExtractor.cpp
 * @brief Fingerprint Feature Extraction & Overlay for Biometric Security
 * @course M.Tech Cryptography and Cyber Security
 * @framework Neurotechnology VeriFinger SDK (v2025.1)
 *
 * REPAIR LOG:
 * 1. Fixed String Output: Using .GetBuffer() directly (returns const NChar*).
 * 2. Fixed Image Conversion: Using static method 'NImage::FromImage(format, src, flags)'.
 * - 'flags' (0) is explicitly required to resolve overload ambiguity.
 * 3. Verified: NPF_RGB_8U is used for 24-bit RGB conversion.
 */

#include <iostream>
#include <vector>

// --- SDK HEADERS ---
#include <NCore.hpp>
#include <NBiometrics.hpp>
#include <NBiometricClient.hpp>
#include <NMedia.hpp>
#include <NLicensing.hpp>

// FIX: Include the PixelFormat C++ definitions
#include <Images/NImage.hpp>
#include <Images/NPixelFormat.hpp>

// --- NAMESPACES ---
using namespace std;
using namespace Neurotec;
using namespace Neurotec::Licensing;
using namespace Neurotec::Biometrics;
using namespace Neurotec::Biometrics::Client; 
using namespace Neurotec::Images;

// --- CONFIGURATION ---
const NString COMPONENTS = N_T("Biometrics.FingerExtraction");
const NString SERVER_ADDR = N_T("/local");
const NString PORT = N_T("5000");

/**
 * @brief Draws a red box overlay directly on the pixel buffer.
 * Uses direct memory access for performance (critical in crypto-biometrics).
 */
void DrawOverlay(NImage &image, int x, int y) {
    // 1. Check Format: Must be RGB (3 channels, 8 bits each)
    // FIX: Use 'NPF_RGB_8U' and compare raw values
    if (image.GetPixelFormat().GetValue() != NPF_RGB_8U.GetValue()) return;

    // 2. Memory Access
    NUInt stride = image.GetStride();
    // GetPixels() returns NBuffer, which still requires GetPtr() to get void*
    void* bufferPtr = image.GetPixels().GetPtr(); 
    NByte* bytePixels = (NByte*)bufferPtr;

    int width = (int)image.GetWidth();
    int height = (int)image.GetHeight();
    int boxSize = 3; 

    // 3. Drawing Logic (Red Box)
    for (int i = -boxSize; i <= boxSize; i++) {
        for (int j = -boxSize; j <= boxSize; j++) {
            int px = x + i;
            int py = y + j;

            if (px >= 0 && px < width && py >= 0 && py < height) {
                if (abs(i) == boxSize || abs(j) == boxSize) {
                    // Pointer Arithmetic: Base + Row_Offset + Col_Offset
                    // Note: 'px * 3' because we are in RGB mode (3 bytes per pixel)
                    NByte* pixelPtr = bytePixels + (py * stride) + (px * 3);
                    
                    // Set RGB values to RED
                    pixelPtr[0] = 0;   // Blue
                    pixelPtr[1] = 0;   // Green
                    pixelPtr[2] = 255; // Red
                }
            }
        }
    }
}

int main(int argc, char **argv) {
    // Use wide output (wcout) for Unicode compatibility
    if (argc < 2) {
        wcout << N_T("Usage: MinutiaeExtractor <fingerprint_image_path>") << endl;
        return 1;
    }

    bool available = false;

    try {
        // 1. LICENSE ACQUISITION
        // FIX: Removed .GetPtr() because GetBuffer() returns the pointer directly
        wcout << N_T("[System] Obtaining license: ") << COMPONENTS.GetBuffer() << endl;
        available = NLicense::ObtainComponents(SERVER_ADDR, PORT, COMPONENTS);

        if (!available) {
            wcout << N_T("[Error] Could not obtain license.") << endl;
            return 1;
        }

        // 2. SETUP ENGINE
        NBiometricClient client;
        client.SetBiometricTypes(nbtFinger);
        client.SetUseDeviceManager(false);

        // 3. PREPARE INPUT
        NSubject subject;
        NFinger finger;
        finger.SetFileName(argv[1]); 
        subject.GetFingers().Add(finger);

        // FIX: Removed .GetPtr()
        wcout << N_T("[System] Processing: ") << NString(argv[1]).GetBuffer() << endl;

        // 4. EXTRACT FEATURES (Minutiae)
        NBiometricStatus status = client.CreateTemplate(subject);

        if (status == nbsOk) {
            wcout << N_T("[Success] Extraction complete.") << endl;

            // 5. GET DATA
            auto processedFinger = subject.GetFingers().Get(0);
            auto image = processedFinger.GetImage(); 
            
            // Convert to RGB for visualization
            // FIX: Use NImage::FromImage with explicit flags (0)
            // Biometric engines use Grayscale (8-bit), but we need RGB (24-bit) for red overlays.
            auto rgbImage = NImage::FromImage(NPF_RGB_8U, image, 0);

            auto attributes = processedFinger.GetObjects().Get(0);
            auto nTemplate = attributes.GetTemplate();
            auto minutiae = nTemplate.GetMinutiae();

            int count = minutiae.GetCount();
            wcout << N_T("\n--- CRYPTOGRAPHIC FEATURE ANALYSIS ---") << endl;
            wcout << N_T("Features Detected: ") << count << endl;
            wcout << N_T("ID \t X \t Y \t Angle \t Type") << endl;
            wcout << N_T("---------------------------------------") << endl;

            // 6. PROCESS & DRAW
            for (int i = 0; i < count; i++) {
                auto m = minutiae.Get(i);
                double degrees = (m.Angle * 360.0) / 256.0;

                if (i < 5) {
                    const NChar* typeStr = (m.Type == nfmtBifurcation ? N_T("Bif") : N_T("End"));
                    wcout << i << N_T("\t ") << m.X << N_T("\t ") << m.Y << N_T("\t ") 
                          << (int)degrees << N_T("\t ") << typeStr << endl;
                }

                DrawOverlay(rgbImage, m.X, m.Y);
            }

            // 7. SAVE ARTIFACT
            NString outputPath = N_T("overlay_output.jpg");
            rgbImage.Save(outputPath);
            // FIX: Removed .GetPtr()
            wcout << N_T("\n[Output] Saved to: ") << outputPath.GetBuffer() << endl;

        } else {
            // Use integer status code
            wcout << N_T("[Failed] Status Code: ") << (int)status << endl;
        }

        NLicense::ReleaseComponents(COMPONENTS);

    } catch (NError& ex) {
        // FIX: Removed .GetPtr()
        wcout << N_T("[Exception] ") << ex.GetMessage().GetBuffer() << endl;
        NLicense::ReleaseComponents(COMPONENTS);
    }

    return 0;
}