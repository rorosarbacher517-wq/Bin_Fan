from __future__ import annotations


def require_tensorflow():
    try:
        import tensorflow as tf
    except Exception as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(f"TensorFlow is required for the Keras temporal graph model: {exc!r}") from exc
    return tf


def make_tf_patchtst_graphsage_model(
    n_weather: int,
    n_node: int,
    n_classes: int = 4,
    window: int = 24,
    patch_len: int = 6,
    d_model: int = 64,
    hidden: int = 96,
    n_heads: int = 4,
):
    """Create a TensorFlow/Keras PatchTST + GraphSAGE model.

    The model consumes all towers for one timestamp:
    - x_seq: [nodes, window, weather_features]
    - x_node: [nodes, node_features], including IEEE738/DLR priors
    - edge_index: [2, directed_edges]
    """
    tf = require_tensorflow()
    if window % patch_len != 0:
        raise ValueError("window must be divisible by patch_len for the TensorFlow model")

    class PatchEncoder(tf.keras.layers.Layer):
        def __init__(self) -> None:
            super().__init__()
            self.reshape = tf.keras.layers.Reshape((window // patch_len, patch_len * n_weather))
            self.proj = tf.keras.layers.Dense(d_model)
            self.attn = tf.keras.layers.MultiHeadAttention(num_heads=n_heads, key_dim=max(d_model // n_heads, 1))
            self.norm1 = tf.keras.layers.LayerNormalization()
            self.ffn = tf.keras.Sequential(
                [
                    tf.keras.layers.Dense(d_model * 2, activation="relu"),
                    tf.keras.layers.Dense(d_model),
                ]
            )
            self.norm2 = tf.keras.layers.LayerNormalization()

        def call(self, x, training=False):
            patches = self.reshape(x)
            z = self.proj(patches)
            z = self.norm1(z + self.attn(z, z, training=training))
            z = self.norm2(z + self.ffn(z, training=training))
            return tf.reduce_mean(z, axis=1)

    class GraphSageLayer(tf.keras.layers.Layer):
        def __init__(self, out_dim: int) -> None:
            super().__init__()
            self.self_proj = tf.keras.layers.Dense(out_dim)
            self.neigh_proj = tf.keras.layers.Dense(out_dim)

        def call(self, h, edge_index):
            src = edge_index[0]
            dst = edge_index[1]
            n_nodes = tf.shape(h)[0]
            neigh = tf.math.unsorted_segment_sum(tf.gather(h, src), dst, n_nodes)
            deg = tf.math.unsorted_segment_sum(tf.ones((tf.shape(dst)[0], 1), dtype=h.dtype), dst, n_nodes)
            neigh = neigh / tf.maximum(deg, 1.0)
            return tf.nn.relu(self.self_proj(h) + self.neigh_proj(neigh))

    class TFPatchTSTGraphSAGE(tf.keras.Model):
        def __init__(self) -> None:
            super().__init__()
            self.temporal = PatchEncoder()
            self.node_proj = tf.keras.Sequential(
                [
                    tf.keras.layers.Dense(d_model, activation="relu"),
                    tf.keras.layers.LayerNormalization(),
                ]
            )
            self.sage1 = GraphSageLayer(hidden)
            self.sage2 = GraphSageLayer(hidden)
            self.head = tf.keras.Sequential(
                [
                    tf.keras.layers.LayerNormalization(),
                    tf.keras.layers.Dense(n_classes),
                ]
            )

        def call(self, inputs, training=False):
            x_seq, x_node, edge_index = inputs
            z_time = self.temporal(x_seq, training=training)
            z_node = self.node_proj(x_node, training=training)
            h = tf.concat([z_time, z_node], axis=-1)
            h = self.sage1(h, edge_index)
            h = self.sage2(h, edge_index)
            return self.head(h, training=training)

    return TFPatchTSTGraphSAGE()
