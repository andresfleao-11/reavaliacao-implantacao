package com.reavaliacao.rfidmiddleware.di

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.preferencesDataStore
import androidx.room.Room
import com.reavaliacao.rfidmiddleware.data.SettingsDataStore
import com.reavaliacao.rfidmiddleware.data.local.AppDatabase
import com.reavaliacao.rfidmiddleware.data.local.TagDao
import com.reavaliacao.rfidmiddleware.data.remote.ApiService
import com.reavaliacao.rfidmiddleware.data.remote.DynamicBaseUrlInterceptor
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): AppDatabase {
        return Room.databaseBuilder(
            context,
            AppDatabase::class.java,
            "rfid_middleware_db"
        ).build()
    }

    @Provides
    @Singleton
    fun provideTagDao(database: AppDatabase): TagDao {
        return database.tagDao()
    }

    @Provides
    @Singleton
    fun provideSettingsDataStore(dataStore: DataStore<Preferences>): SettingsDataStore {
        return SettingsDataStore(dataStore)
    }

    @Provides
    @Singleton
    fun provideDynamicBaseUrlInterceptor(settingsDataStore: SettingsDataStore): DynamicBaseUrlInterceptor {
        return DynamicBaseUrlInterceptor(settingsDataStore)
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(dynamicBaseUrlInterceptor: DynamicBaseUrlInterceptor): OkHttpClient {
        val loggingInterceptor = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        return OkHttpClient.Builder()
            .addInterceptor(dynamicBaseUrlInterceptor)
            .addInterceptor(loggingInterceptor)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(okHttpClient: OkHttpClient): Retrofit {
        // URL base placeholder - substituida dinamicamente pelo DynamicBaseUrlInterceptor
        return Retrofit.Builder()
            .baseUrl("http://placeholder.local/")
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    @Provides
    @Singleton
    fun provideApiService(retrofit: Retrofit): ApiService {
        return retrofit.create(ApiService::class.java)
    }

    @Provides
    @Singleton
    fun provideDataStore(@ApplicationContext context: Context): DataStore<Preferences> {
        return context.dataStore
    }
}
