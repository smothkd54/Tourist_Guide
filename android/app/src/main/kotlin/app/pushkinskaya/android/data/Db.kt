package app.pushkinskaya.android.data

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "landmarks")
data class LandmarkEntity(
    @PrimaryKey val id: String,
    val name: String,
    val nameRu: String,
    val type: String,
    val lat: Double,
    val lon: Double,
    val address: String,
    val description: String,
    val funFact: String,
    val yearBuilt: Int?,
    val style: String,
    val architect: String,
    val status: String?,
)

/** The visit list: one row per landmark, in the order the user added them. */
@Entity(tableName = "route_items")
data class RouteItemEntity(
    @PrimaryKey val landmarkId: String,
    val position: Int,
)

@Dao
interface LandmarkDao {
    @Query("SELECT * FROM landmarks ORDER BY name")
    fun observeAll(): Flow<List<LandmarkEntity>>

    @Query("SELECT * FROM landmarks WHERE id = :id")
    fun observe(id: String): Flow<LandmarkEntity?>

    @Query("SELECT * FROM landmarks")
    suspend fun getAll(): List<LandmarkEntity>

    @Upsert
    suspend fun upsertAll(items: List<LandmarkEntity>)
}

@Dao
interface RouteDao {
    @Query("SELECT * FROM route_items ORDER BY position")
    fun observe(): Flow<List<RouteItemEntity>>

    @Query("SELECT * FROM route_items ORDER BY position")
    suspend fun getAll(): List<RouteItemEntity>

    @Query("SELECT COALESCE(MAX(position), -1) + 1 FROM route_items")
    suspend fun nextPosition(): Int

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun add(item: RouteItemEntity)

    @Query("DELETE FROM route_items WHERE landmarkId = :id")
    suspend fun remove(id: String)

    @Query("DELETE FROM route_items")
    suspend fun clear()
}

@Database(entities = [LandmarkEntity::class, RouteItemEntity::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun landmarkDao(): LandmarkDao
    abstract fun routeDao(): RouteDao
}
