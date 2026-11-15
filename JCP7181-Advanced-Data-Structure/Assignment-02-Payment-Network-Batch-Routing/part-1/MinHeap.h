#pragma once
#include <vector>
#include <utility>


class MinHeap {
    std::vector<std::pair<long long, int>> heap;

    void heapifyUp(int index) {
        while (index > 0) {
            int parent = (index - 1) / 2;
            if (heap[parent].first <= heap[index].first) break;
            std::swap(heap[parent], heap[index]);
            index = parent;
        }
    }

    void heapifyDown(int index) {
        int n = heap.size();
        while (true) {
            int smallest = index;
            int left = 2 * index + 1, right = 2 * index + 2;
            if (left < n && heap[left].first < heap[smallest].first) smallest = left;
            if (right < n && heap[right].first < heap[smallest].first) smallest = right;
            if (smallest == index) break;
            std::swap(heap[smallest], heap[index]);
            index = smallest;
        }
    }

public:
    void push(std::pair<long long, int> kv) {
        heap.push_back(kv);
        heapifyUp(heap.size() - 1);
    }

    void pop() {
        if (heap.empty()) return;
        heap[0] = heap.back();
        heap.pop_back();
        if (!heap.empty())
            heapifyDown(0);
    }

    std::pair<long long, int> top() const {
        return heap.front();
    }

    bool empty() const {
        return heap.empty();
    }
};
