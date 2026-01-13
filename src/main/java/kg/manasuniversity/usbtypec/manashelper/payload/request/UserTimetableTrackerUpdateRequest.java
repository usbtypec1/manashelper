package kg.manasuniversity.usbtypec.manashelper.payload.request;

import jakarta.validation.constraints.Size;

import java.util.List;

public record UserTimetableTrackerUpdateRequest(
        @Size(max = 5, message = "Course IDs list must contain between 1 and 5 items")
        List<Integer> courseIds
) {
}
