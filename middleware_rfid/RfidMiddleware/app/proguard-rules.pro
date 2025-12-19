# Add project specific ProGuard rules here.

# Chainway SDK
-keep class com.rscja.** { *; }
-dontwarn com.rscja.**

# Retrofit
-keepattributes Signature
-keepattributes *Annotation*
-keep class retrofit2.** { *; }
-keepclasseswithmembers class * {
    @retrofit2.http.* <methods>;
}

# Gson
-keep class com.google.gson.** { *; }
-keep class * implements com.google.gson.TypeAdapterFactory
-keep class * implements com.google.gson.JsonSerializer
-keep class * implements com.google.gson.JsonDeserializer

# Room
-keep class * extends androidx.room.RoomDatabase
-dontwarn androidx.room.paging.**

# Data classes
-keep class com.reavaliacao.rfidmiddleware.data.remote.** { *; }
-keep class com.reavaliacao.rfidmiddleware.data.local.** { *; }
