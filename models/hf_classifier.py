import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

MODEL_NAME = "aalonso-developer/vit-base-clothing-leafs-example-full-simple_highres"

# Map labels to categories
LABEL_TO_CATEGORY = {
    "Skirt": "Bottomwear",
    "Jodhpurs": "Bottomwear",
    "Leggings": "Bottomwear",
    "Dress": "Dresses",
    "Sweatshorts": "Bottomwear",
    "Tee": "Topwear",
    "Jersey": "Topwear",
    "Sweatpants": "Bottomwear",
    "Sarong": "Dresses",
    "Tank": "Topwear",
    "Poncho": "Outerwear",
    "Anorak": "Outerwear",
    "Kimono": "Outerwear",
    "Romper": "Dresses",
    "Top": "Topwear",
    "Culottes": "Bottomwear",
    "Robe": "Outerwear",
    "Shorts": "Bottomwear",
    "Jeans": "Bottomwear",
    "Cardigan": "Outerwear",
    "Jumpsuit": "Dresses",
    "Sweater": "Topwear",
    "Bomber": "Outerwear",
    "Parka": "Outerwear",
    "Chinos": "Bottomwear",
    "Turtleneck": "Topwear",
    "Blouse": "Topwear",
    "Blazer": "Outerwear",
    "Hoodie": "Outerwear",
    "Coat": "Outerwear",
    "Peacoat": "Outerwear",
    "Jacket": "Outerwear",
    "Button-Down": "Topwear",
    "Kaftan": "Dresses",
    # Add other mappings as needed
}

def load_image(image_path):
    return Image.open(image_path).convert("RGB")

def classify_image(image_path):
    processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
    model = AutoModelForImageClassification.from_pretrained(MODEL_NAME)

    image = load_image(image_path)
    inputs = processor(image, return_tensors="pt")

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        probabilities = torch.softmax(logits, dim=-1)

    top_prediction = probabilities[0].topk(1)
    label_idx = top_prediction.indices[0].item()
    score = top_prediction.values[0].item()

    label = model.config.id2label[label_idx]
    category = LABEL_TO_CATEGORY.get(label, "Unknown")

    return {
        "label": label,
        "score": score,
        "category": category,
    }
