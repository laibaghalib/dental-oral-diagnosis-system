import os
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
 
import base64
import numpy as np
import cv2
import tensorflow as tf
from tensorflow.keras import layers, Model, applications
from tensorflow.keras.applications import DenseNet121
 
# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────
IMG_SIZE    = (224, 224)
NUM_CLASSES = 6
CLASS_NAMES = [
    'Calculus', 'Data caries', 'Gingivitis',
    'Mouth Ulcer', 'Tooth Discoloration', 'hypodontia'
]
 
ENSEMBLE_WEIGHTS = [0.31, 0.32, 0.37]
 
BASE_DIR          = os.path.dirname(os.path.abspath(__file__))
RESNET_PATH       = os.path.join(BASE_DIR, 'resnet18.h5')
DENSENET_PATH     = os.path.join(BASE_DIR, 'densenet121.h5')
EFFICIENTNET_PATH = os.path.join(BASE_DIR, 'efficientnetv2_vit_style.h5')
 
 
# ─────────────────────────────────────────────
# Model Architectures
# ─────────────────────────────────────────────
def conv_block(filters, strides=1, drop_rate=0.1):
    def block(x):
        shortcut = x
        x = layers.Conv2D(filters, 3, strides=strides, padding='same')(x)
        x = layers.BatchNormalization()(x)
        x = layers.Activation('relu')(x)
        x = layers.Conv2D(filters, 3, padding='same')(x)
        x = layers.BatchNormalization()(x)
        x = layers.Dropout(drop_rate)(x)
        if strides != 1 or shortcut.shape[-1] != filters:
            shortcut = layers.Conv2D(filters, 1, strides=strides, padding='same')(shortcut)
            shortcut = layers.BatchNormalization()(shortcut)
        x = layers.Add()([x, shortcut])
        x = layers.Activation('relu')(x)
        return x
    return block
 
def build_resnet18():
    inputs = layers.Input(shape=(224, 224, 3))
    x = layers.Conv2D(64, 7, strides=2, padding='same')(inputs)
    x = layers.BatchNormalization()(x)
    x = layers.Activation('relu')(x)
    x = layers.MaxPooling2D(3, strides=2, padding='same')(x)
    x = conv_block(64)(x);  x = conv_block(64)(x)
    x = conv_block(128, strides=2)(x); x = conv_block(128)(x)
    x = conv_block(256, strides=2)(x); x = conv_block(256)(x)
    x = conv_block(512, strides=2)(x); x = conv_block(512)(x)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.5)(x)
    x = layers.Dense(256, activation='relu')(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(NUM_CLASSES, activation='softmax')(x)
    return Model(inputs, outputs, name='resnet18')
 
def build_densenet():
    base = DenseNet121(weights=None, include_top=False, input_shape=(224, 224, 3))
    x = base.output
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.5)(x)
    x = layers.Dense(512, activation='relu')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.4)(x)
    x = layers.Dense(256, activation='relu')(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(NUM_CLASSES, activation='softmax')(x)
    return Model(inputs=base.input, outputs=outputs, name='densenet121')
 
def build_efficientnet_vit():
    inputs   = layers.Input(shape=(224, 224, 3))
    backbone = applications.EfficientNetV2B1(include_top=False, weights=None)
    backbone.trainable = True
    x = backbone(inputs, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.4)(x)
    x = layers.Reshape((1, 1, x.shape[-1]))(x)
    attention = layers.MultiHeadAttention(num_heads=8, key_dim=64)(x, x)
    attention = layers.LayerNormalization(epsilon=1e-6)(attention + x)
    x = layers.Reshape((-1,))(attention)
    x = layers.Dense(512, activation="gelu")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.5)(x)
    outputs = layers.Dense(NUM_CLASSES, activation="softmax")(x)
    return Model(inputs, outputs, name='efficientnetv2_vit')
 
 
# ─────────────────────────────────────────────
# Singleton Model Loader
# ─────────────────────────────────────────────
_models = None
 
def load_models():
    global _models
    if _models is not None:
        return _models
 
    print("[Models] Loading all three models...")
    m1 = build_resnet18();         m1.load_weights(RESNET_PATH)
    print("[Models] ResNet18 loaded.")
    m2 = build_densenet();         m2.load_weights(DENSENET_PATH)
    print("[Models] DenseNet121 loaded.")
    m3 = build_efficientnet_vit(); m3.load_weights(EFFICIENTNET_PATH)
    print("[Models] EfficientNetV2-ViT loaded.")
 
    _models = (m1, m2, m3)
    return _models
 
 
# ─────────────────────────────────────────────
# Preprocessing
# ─────────────────────────────────────────────
def preprocess(img_array):
    img = cv2.resize(img_array, IMG_SIZE)
    img = img.astype(np.float32) / 255.0
    return np.expand_dims(img, axis=0)
 
 
# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def array_to_b64(img_bgr):
    _, buf = cv2.imencode('.png', img_bgr)
    return base64.b64encode(buf).decode('utf-8')
 
def heatmap_to_overlay(original_rgb, heatmap_2d):
    h        = cv2.resize(heatmap_2d, (224, 224))
    h        = np.uint8(255 * np.clip(h, 0, 1))
    colored  = cv2.applyColorMap(h, cv2.COLORMAP_JET)
    orig_bgr = cv2.cvtColor(cv2.resize(original_rgb, (224, 224)), cv2.COLOR_RGB2BGR)
    return cv2.addWeighted(orig_bgr, 0.6, colored, 0.4, 0)
 
def _normalise(heatmap):
    heatmap = np.maximum(heatmap, 0)
    mx = heatmap.max()
    if mx == 0:
        return None
    return cv2.resize((heatmap / mx).astype(np.float32), (224, 224))
 
def _activation_map(conv_np):
    """Real fallback: channel-mean of positive activations. conv_np: (1,H,W,C)"""
    act = np.mean(np.maximum(conv_np[0], 0), axis=-1)
    return _normalise(act)
 
def _replay_head(head_layers, x):
    """
    Replay ViT head layers one by one.
    MultiHeadAttention needs (query, value) — we pass (x, x).
    LayerNormalization with a residual Add must be handled too.
    We track the tensor before attention to reconstruct the residual.
    """
    pre_attention = None
    for lyr in head_layers:
        if isinstance(lyr, tf.keras.layers.MultiHeadAttention):
            pre_attention = x
            x = lyr(x, x, training=False)
        elif isinstance(lyr, tf.keras.layers.Add):
            if pre_attention is not None:
                x = x + pre_attention
                pre_attention = None
        else:
            try:
                x = lyr(x, training=False)
            except TypeError:
                x = lyr(x)
    return x
 
 
# ─────────────────────────────────────────────
# Tooth Area Estimation
# ─────────────────────────────────────────────
def estimate_tooth_area(heatmap_2d):
    """
    Map the brightest point in the ensemble GradCAM heatmap
    to a human-readable dental region string.
 
    The 224x224 heatmap is divided into a 3x3 grid:
      Vertical   : Upper (0-74)  | Middle (75-149) | Lower (150-224)
      Horizontal : Left  (0-74)  | Center (75-149) | Right  (150-224)
 
    Returns a string like "Upper Left Region".
    """
    if heatmap_2d is None or heatmap_2d.max() == 0:
        return "Region undetermined"
 
    y, x = np.unravel_index(heatmap_2d.argmax(), heatmap_2d.shape)
 
    if y < 75:
        vertical = "Upper"
    elif y < 150:
        vertical = "Middle"
    else:
        vertical = "Lower"
 
    if x < 75:
        horizontal = "Left"
    elif x < 150:
        horizontal = "Center"
    else:
        horizontal = "Right"
 
    return f"{vertical} {horizontal} Region"
 
 
# ─────────────────────────────────────────────
# GradCAM — flat CNN (ResNet18, DenseNet121)
# ─────────────────────────────────────────────
def gradcam_for_cnn(model, img_tensor):
    img_tensor = tf.cast(img_tensor, tf.float32)
 
    last_conv = next(
        (l for l in reversed(model.layers)
         if isinstance(l, tf.keras.layers.Conv2D)), None
    )
    if last_conv is None:
        return np.zeros((224, 224), dtype=np.float32)
 
    try:
        grad_model = tf.keras.Model(
            inputs=model.inputs,
            outputs=[last_conv.output, model.output]
        )
        with tf.GradientTape() as tape:
            conv_out, preds = grad_model(img_tensor, training=False)
            tape.watch(conv_out)
            class_channel = preds[:, tf.argmax(preds[0])]
 
        grads = tape.gradient(class_channel, conv_out)
 
        if grads is None:
            result = _activation_map(conv_out.numpy())
            return result if result is not None else np.zeros((224, 224), dtype=np.float32)
 
        pooled  = tf.reduce_mean(grads, axis=(0, 1, 2))
        heatmap = (conv_out[0] @ pooled[..., tf.newaxis]).numpy().squeeze()
        result  = _normalise(heatmap)
        if result is not None:
            return result
 
        result = _activation_map(conv_out.numpy())
        return result if result is not None else np.zeros((224, 224), dtype=np.float32)
 
    except Exception as e:
        print(f"[GradCAM] {model.name} error: {e}")
        return np.zeros((224, 224), dtype=np.float32)
 
 
# ─────────────────────────────────────────────
# GradCAM++ — EfficientNetV2-ViT
# ─────────────────────────────────────────────
def gradcam_for_efficientnet(model, img_tensor):
    """
    Real GradCAM++ for the CNN-ViT hybrid.
 
    The previous failure: 'missing a required argument: value'
    ──────────────────────────────────────────────────────────
    MultiHeadAttention in this TF version requires explicit
    (query, value) positional args when called imperatively.
    The generic `lyr(x, training=False)` only passes query,
    causing the crash. Fixed in _replay_head() above by
    detecting MultiHeadAttention and calling lyr(x, x, ...).
 
    Graph strategy (same as before, now with fixed head replay):
    ─────────────────────────────────────────────────────────────
    - backbone_grad built entirely inside backbone's own graph
      (backbone.input → [last_conv.output, backbone.output])
    - img_tensor fed directly to backbone_grad (same shape)
    - Head layers replayed with _replay_head() which handles MHA
    - GradCAM++ → plain GradCAM → activation map fallback chain
    """
    img_tensor     = tf.cast(img_tensor, tf.float32)
    backbone_layer = model.layers[1]
 
    last_conv_name = None
    for lyr in reversed(backbone_layer.layers):
        if isinstance(lyr, tf.keras.layers.Conv2D):
            last_conv_name = lyr.name
            break
 
    if last_conv_name is None:
        print("  [!] No Conv2D in backbone")
        return np.zeros((224, 224), dtype=np.float32)
 
    print(f"  [GradCAM] target conv: {last_conv_name}")
 
    try:
        internal_conv = backbone_layer.get_layer(last_conv_name)
        backbone_grad = tf.keras.Model(
            inputs=backbone_layer.input,
            outputs=[internal_conv.output, backbone_layer.output],
            name='bb_grad'
        )
    except Exception as e:
        print(f"  [!] backbone_grad build failed: {e}")
        return np.zeros((224, 224), dtype=np.float32)
 
    head_layers = []
    found = False
    for lyr in model.layers:
        if lyr is backbone_layer:
            found = True
            continue
        if found and not isinstance(lyr, tf.keras.layers.InputLayer):
            head_layers.append(lyr)
 
    try:
        with tf.GradientTape() as tape:
            conv_out, bb_feats = backbone_grad(img_tensor, training=False)
            tape.watch(conv_out)
            preds         = _replay_head(head_layers, bb_feats)
            pred_idx      = tf.argmax(preds[0])
            class_channel = preds[:, pred_idx]
 
        grads    = tape.gradient(class_channel, conv_out)
        conv_np  = conv_out.numpy()
 
        if grads is None:
            print("  [!] Gradients None → activation map")
            result = _activation_map(conv_np)
            return result if result is not None else np.zeros((224, 224), dtype=np.float32)
 
        grads_np = grads.numpy()
 
        # ── GradCAM++ ──────────────────────────────────────────────────
        grads_sq  = grads_np ** 2
        grads_cu  = grads_np ** 3
        denom     = 2.0 * grads_sq + conv_np * grads_cu
        denom     = np.where(denom != 0.0, denom, 1e-10)
        alphas    = grads_sq / denom
        alpha_sum = np.sum(alphas, axis=(1, 2), keepdims=True)
        alpha_sum = np.where(alpha_sum != 0, alpha_sum, 1e-10)
        alphas   /= alpha_sum
        weights   = np.sum(alphas * np.maximum(grads_np, 0), axis=(1, 2))
        heatmap   = np.sum(conv_np[0] * weights[0], axis=-1)
 
        result = _normalise(heatmap)
        if result is not None:
            print("  [GradCAM] GradCAM++ succeeded ✓")
            return result
 
        # ── Plain GradCAM fallback ─────────────────────────────────────
        pooled  = np.mean(grads_np, axis=(0, 1, 2))
        heatmap = np.sum(conv_np[0] * pooled, axis=-1)
        result  = _normalise(heatmap)
        if result is not None:
            return result
 
        # ── Activation map fallback  ─────────────────
        result = _activation_map(conv_np)
        return result if result is not None else np.zeros((224, 224), dtype=np.float32)
 
    except Exception as e:
        print(f"[GradCAM] EfficientNet error: {e}")
        return np.zeros((224, 224), dtype=np.float32)
 
 
# ─────────────────────────────────────────────
# Main Predict Function
# ─────────────────────────────────────────────
def predict(img_array):
    m1, m2, m3 = load_models()
    tensor = preprocess(img_array)
 
    p1 = m1.predict(tensor, verbose=0)[0]
    p2 = m2.predict(tensor, verbose=0)[0]
    p3 = m3.predict(tensor, verbose=0)[0]
 
    ensemble = (
        ENSEMBLE_WEIGHTS[0] * p1 +
        ENSEMBLE_WEIGHTS[1] * p2 +
        ENSEMBLE_WEIGHTS[2] * p3
    )
    pred_idx       = int(np.argmax(ensemble))
    confidence_pct = round(float(ensemble[pred_idx]) * 100, 2)
    predicted_cls  = CLASS_NAMES[pred_idx]
    print(f"[Ensemble] {predicted_cls} — {confidence_pct}%")
 
    print("[GradCAM] Computing...")
    h1 = gradcam_for_cnn(m1, tensor)
    h2 = gradcam_for_cnn(m2, tensor)
    h3 = gradcam_for_efficientnet(m3, tensor)
    print(f"[GradCAM] R={h1.max():.3f}  D={h2.max():.3f}  E={h3.max():.3f}")
 
    gradcam_resnet       = array_to_b64(heatmap_to_overlay(img_array, h1)) if h1.max() > 0 else None
    gradcam_densenet     = array_to_b64(heatmap_to_overlay(img_array, h2)) if h2.max() > 0 else None
    gradcam_efficientnet = array_to_b64(heatmap_to_overlay(img_array, h3)) if h3.max() > 0 else None
 
    gradcam_ensemble = None
    avg_heatmap      = None
 
    valid_heatmaps = [
        (h, w) for h, w in [
            (h1, ENSEMBLE_WEIGHTS[0]),
            (h2, ENSEMBLE_WEIGHTS[1]),
            (h3, ENSEMBLE_WEIGHTS[2]),
        ] if h.max() > 0
    ]
    if valid_heatmaps:
        total_w     = sum(w for _, w in valid_heatmaps)
        avg_heatmap = sum(h * (w / total_w) for h, w in valid_heatmaps)
        avg_heatmap /= avg_heatmap.max() + 1e-8
        gradcam_ensemble = array_to_b64(heatmap_to_overlay(img_array, avg_heatmap))
 
    # ── Tooth Area Estimation ─────────────────────────────────────────
    tooth_area = estimate_tooth_area(avg_heatmap) if avg_heatmap is not None else "Region undetermined"
    print(f"[ToothArea] {tooth_area}")
 
    print("[GradCAM] Done.")
 
    return {
        'predicted_class': predicted_cls,
        'confidence':      confidence_pct,
        'tooth_area':      tooth_area,
 
        'all_probabilities': {
            CLASS_NAMES[i]: round(float(ensemble[i]) * 100, 2)
            for i in range(NUM_CLASSES)
        },
 
        'individual_predictions': {
            'ResNet18':       CLASS_NAMES[int(np.argmax(p1))],
            'DenseNet121':    CLASS_NAMES[int(np.argmax(p2))],
            'EfficientNetV2': CLASS_NAMES[int(np.argmax(p3))],
        },
 
        'individual_confidences': {
            'ResNet18':       round(float(p1.max()) * 100, 2),
            'DenseNet121':    round(float(p2.max()) * 100, 2),
            'EfficientNetV2': round(float(p3.max()) * 100, 2),
        },
 
        'gradcam': {
            'resnet18':       gradcam_resnet,
            'densenet121':    gradcam_densenet,
            'efficientnetv2': gradcam_efficientnet,
            'ensemble':       gradcam_ensemble,
        },
    }