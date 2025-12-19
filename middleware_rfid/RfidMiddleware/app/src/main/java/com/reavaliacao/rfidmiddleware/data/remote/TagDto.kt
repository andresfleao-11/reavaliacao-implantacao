package com.reavaliacao.rfidmiddleware.data.remote

import com.google.gson.annotations.SerializedName

data class TagDto(
    @SerializedName("epc")
    val epc: String,

    @SerializedName("rssi")
    val rssi: String,

    @SerializedName("timestamp")
    val timestamp: String
)

data class TagBatchRequest(
    @SerializedName("device_id")
    val deviceId: String,

    @SerializedName("tags")
    val tags: List<TagDto>,

    @SerializedName("batch_id")
    val batchId: String,

    @SerializedName("location")
    val location: String? = null
)

data class TagBatchResponse(
    @SerializedName("success")
    val success: Boolean,

    @SerializedName("message")
    val message: String?,

    @SerializedName("received_count")
    val receivedCount: Int?
)
