import torch
import torchvision.transforms as transforms
import torchvision.models as models
from PIL import Image
import base64
import io
import os

class CVEngine:
    def __init__(self):
        print("[CVEngine] Loading MobileNetV3-Small (CPU)...")
        # Load a lightweight pre-trained model
        self.model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)
        self.model.eval()
        
        # Standard ImageNet transforms
        self.preprocess = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        print("[CVEngine] Model Loaded.")

    def decode_image(self, image_data: str) -> Image.Image:
        """Decodes base64 string or loads from file path."""
        if os.path.exists(image_data):
            return Image.open(image_data).convert("RGB")
        
        if image_data.startswith("data:image"):
            image_data = image_data.split(",")[1]
            
        image_bytes = base64.b64decode(image_data)
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")

    def estimate_severity(self, image_data: str) -> int:
        """
        Estimates water severity (0-3).
        Since this is a standard ImageNet model (not fine-tuned for floods),
        we simulate the severity mapping for the PoC. In production, 
        you would replace this logic with the fine-tuned flood classification layer.
        """
        if not image_data:
            return 0
            
        try:
            image = self.decode_image(image_data)
            input_tensor = self.preprocess(image)
            input_batch = input_tensor.unsqueeze(0)

            with torch.no_grad():
                output = self.model(input_batch)
                
            # For the PoC, we will hash the top predicted class index 
            # to deterministically return a mock severity score (0-3).
            # This proves the architecture works and can process the image.
            top_class = torch.argmax(output[0]).item()
            mock_severity = top_class % 4 
            
            return mock_severity
            
        except Exception as e:
            print(f"[CVEngine] Error processing image: {e}")
            return 0
