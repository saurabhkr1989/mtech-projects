import torch
import torch.nn as nn
import torchvision.models as models

class SEBlock(nn.Module):
    """
    Squeeze-and-Excitation channel attention block.
    """
    def __init__(self, in_channels, reduction=16):
        super(SEBlock, self).__init__()
        # Squeeze: Global Average Pooling (H_in * W_in -> 1 * 1)
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        
        # Excitation: Adaptive Re-weighting using fully connected layers
        self.fc = nn.Sequential(
            nn.Linear(in_channels, in_channels // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(in_channels // reduction, in_channels, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x):
        b, c, _, _ = x.size()
        
        # Squeeze
        y = self.avg_pool(x).view(b, c)
        
        # Excitation
        y = self.fc(y).view(b, c, 1, 1)
        
        # Scale original feature map
        return x * y.expand_as(x)

class SEAlexNet(nn.Module):
    """
    Custom AlexNet architecture with a Squeeze-and-Excitation block
    inserted just before the fully connected layers.
    Used for extracting deep features from Face and Iris modalities.
    """
    def __init__(self, pretrained=True, num_classes=1000):
        super(SEAlexNet, self).__init__()
        
        # We load standard AlexNet
        # weights=models.AlexNet_Weights.DEFAULT is modern PyTorch syntax
        if pretrained:
            alexnet = models.alexnet(weights=models.AlexNet_Weights.DEFAULT)
        else:
            alexnet = models.alexnet(weights=None)
            
        # The convolutional backbone (features module in PyTorch AlexNet)
        self.features = alexnet.features
        
        # The pooling layer before classifier
        self.avgpool = alexnet.avgpool
        
        # Insert SE Block after the last Conv layer inside features. 
        # Standard AlexNet finishes with 256 channels at Conv5.
        self.se_block = SEBlock(in_channels=256)
        
        # We replace the classifier if we want fine-tuning, or keep it standard.
        self.classifier = alexnet.classifier
        
        if num_classes != 1000:
            # Change the last layer to match target finetuning classes
            self.classifier[6] = nn.Linear(4096, num_classes)
            
    def forward(self, x):
        # 1. Forward through Conv Layers
        x = self.features(x)
        
        # 2. SE Attention
        x = self.se_block(x)
        
        # 3. Pooling
        x = self.avgpool(x)
        
        # Flatten
        x = torch.flatten(x, 1)
        
        # 4. Classifier fully connected layers
        x = self.classifier(x)
        
        return x

    def extract_features(self, x):
        """
        Extracts the 4096-dimensional output from FC2 layer.
        """
        self.eval()
        with torch.no_grad():
            x = self.features(x)
            x = self.se_block(x)
            x = self.avgpool(x)
            x = torch.flatten(x, 1)
            
            # Pass through the first few layers of the classifier (up to FC2)
            # Standard AlexNet structure: 
            # (0): Dropout
            # (1): Linear(256 * 6 * 6, 4096) -> FC1
            # (2): ReLU
            # (3): Dropout
            # (4): Linear(4096, 4096) -> FC2
            # (5): ReLU
            # (6): Linear(4096, num_classes)
            for i in range(6): 
                x = self.classifier[i](x)
            
            return x

if __name__ == "__main__":
    print("Testing Deep SE-AlexNet Tensor Graph...")
    dummy_input = torch.randn(1, 3, 224, 224)
    model = SEAlexNet(pretrained=False)
    out = model(dummy_input)
    features = model.extract_features(dummy_input)
    print(f"Extraction Dimension: {features.shape}")
    print("SE-AlexNet Architecture OK.")
