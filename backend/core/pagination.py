from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class SwipeHistoryPagination(PageNumberPagination):
    page_size = 10                 # swipes per page
    page_size_query_param = "size" # ?size=20
    max_page_size = 50
