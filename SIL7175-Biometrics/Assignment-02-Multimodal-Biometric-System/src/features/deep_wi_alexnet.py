import torch
import torch.nn as nn
from sys import path
import os

path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import Config

class AlexNet_N(nn.Module):
    """
    Writer-Independent Deep Feature Extractor for Signatures (AlexNet_N).
    - 5 Convolutional Layers
    - 2 Fully Connected Layers (FC1, FC2)
    - Batch Normalization injected immediately before non-linear activations.
    """
    def __init__(self, num_classes=50):
        # num_classes depends on the development set sizes
        super(AlexNet_N, self).__init__()
        
        # Input for BHSig after Preprocess is 170x242 (1 channel)
        
        self.features = nn.Sequential(
            # Conv1
            nn.Conv2d(1, 96, kernel_size=11, stride=4, padding=2),
            nn.BatchNorm2d(96), # BN injected before activation
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=3, stride=2),
            
            # Conv2
            nn.Conv2d(96, 256, kernel_size=5, padding=2),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=3, stride=2),
            
            # Conv3
            nn.Conv2d(256, 384, kernel_size=3, padding=1),
            nn.BatchNorm2d(384),
            nn.ReLU(inplace=True),
            
            # Conv4
            nn.Conv2d(384, 384, kernel_size=3, padding=1),
            nn.BatchNorm2d(384),
            nn.ReLU(inplace=True),
            
            # Conv5
            nn.Conv2d(384, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=3, stride=2),
        )
        
        # Adaptive pooling to ensure fixed linear input regardless of 170x242 dimension
        # A standard AlexNet output before FC is 6x6. 
        self.avgpool = nn.AdaptiveAvgPool2d((6, 6))
        
        self.classifier = nn.Sequential(
            # FC1
            nn.Dropout(),
            nn.Linear(256 * 6 * 6, 4096),
            nn.BatchNorm1d(4096), # BN before ReLU
            nn.ReLU(inplace=True),
            
            # FC2
            nn.Dropout(),
            nn.Linear(4096, 4096),
            nn.BatchNorm1d(4096),
            nn.ReLU(inplace=True),
            
            # Final projection to classes (only during WI training)
            nn.Linear(4096, num_classes),
        )
        
    def forward(self, x):
        x = self.features(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.classifier(x)
        return x

    def extract_features(self, x):
        """
        Extracts Writer-Independent features from FC2 (4096 dimension vector).
        Used during target user SVM training.
        """
        self.eval()
        with torch.no_grad():
            x = self.features(x)
            x = self.avgpool(x)
            x = torch.flatten(x, 1)
            
            # Pass through up to FC2 (Index 0 through 7)
            # 0: Drop, 1: Lin, 2: BN, 3: ReLU, 4: Drop, 5: Lin, 6: BN, 7: ReLU
            for i in range(8):
                x = self.classifier[i](x)
                
            return x

if __name__ == "__main__":
    print("Testing Deep AlexNet_N (Writer Independent) Tensor Graph...")
    # Single channel binary image, size 170x242
    dummy_signature = torch.randn(1, 1, 170, 242)
    model = AlexNet_N()
    
    out = model(dummy_signature)
    features = model.extract_features(dummy_signature)
    print(f"Extraction Dimension: {features.shape}. Should be [1, 4096]")
    print("AlexNet_N Architecture OK.")
